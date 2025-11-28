import csv
import logging
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml
from gradeflow_engine.submissions.models import GradedSubmission, RawSubmission
from natsort import natsorted

from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.schemas.grading import GradingJobResult, GradingJobSpec, JobStatus
from gradeflow_backend.utils.engine import model_dump_minimal

DEFAULT_CALLBACK_TIMEOUT_S = 10
DEFAULT_TIMEOUT_S = 300
DEFAULT_POLL_INTERVAL_S = 1
DEFAULT_NUM_WORKERS = 4

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Job:
    id: str
    spec: GradingJobSpec
    callback_url: str


class InMemoryBaseJobExecutor(GradingJobExecutor):
    """
    Shared in-memory executor with:
      - preview/run prioritized queues
      - worker threads
      - filesystem staging of inputs/outputs
      - standard result parsing and callback

    Subclasses must implement `_invoke_engine(workdir: Path, submissions_csv: Path,
    qset_yaml: Path, rubric_yaml: Path, out_path: Path) -> None`
    which is responsible for producing `out_path` (YAML of graded submissions).
    """

    def __init__(
        self,
        *,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        num_workers: int = DEFAULT_NUM_WORKERS,
        callback_timeout_s: int = DEFAULT_CALLBACK_TIMEOUT_S,
    ) -> None:
        self._timeout_s = timeout_s
        self._poll_interval_s = poll_interval_s
        self._num_workers = max(1, int(num_workers))
        self._callback_timeout_s = callback_timeout_s

        # Queues: preview has higher priority than run
        self._jobs_preview: deque[_Job] = deque()
        self._jobs_run: deque[_Job] = deque()

        # Shared status map
        self._status: dict[str, JobStatus] = {}

        # Concurrency primitives
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._cv = threading.Condition(self._lock)

        # Multiple worker threads
        self._workers: list[threading.Thread] = []
        self._started = False

    # ------- GradingJobExecutor API -------

    def submit(self, spec: GradingJobSpec, callback_url: str) -> str:
        self.start()
        job_id = f"job_{int(time.time() * 1000)}_{spec.type}"
        job = _Job(id=job_id, spec=spec, callback_url=callback_url)
        with self._lock:
            self._status[job_id] = "queued"
            if spec.type == "preview":
                self._jobs_preview.append(job)
            else:
                self._jobs_run.append(job)
            q_preview, q_run = len(self._jobs_preview), len(self._jobs_run)
            logger.info(
                "Job submitted",
                extra={
                    "job_id": job_id,
                    "assessment_id": spec.assessment_id,
                    "type": spec.type,
                    "queues": {"preview": q_preview, "run": q_run},
                },
            )
            self._cv.notify()
        return job_id

    def get_status(self, job_id: str) -> JobStatus:
        with self._lock:
            return self._status.get(job_id, "failed")

    def start(self) -> None:
        if self._started:
            return
        self._stop_event.clear()
        logger.info("Executor starting", extra={"workers": self._num_workers})
        # Spawn N workers
        for i in range(self._num_workers):
            t = threading.Thread(target=self._worker_loop, name=f"GF-Worker-{i}", daemon=True)
            self._workers.append(t)
            t.start()
        self._started = True
        logger.info("Executor started", extra={"workers": self._num_workers})

    def stop(self) -> None:
        logger.info("Executor stopping")
        with self._lock:
            self._stop_event.set()
            self._cv.notify_all()
        for t in self._workers:
            if t.is_alive():
                t.join(timeout=2)
        self._workers.clear()
        self._started = False
        logger.info("Executor stopped")

    # ------- Worker loop -------

    def _set_status(self, job_id: str, status: JobStatus) -> None:
        self._status[job_id] = status

    def _pop_next_locked(self) -> _Job | None:
        if self._jobs_preview:
            return self._jobs_preview.popleft()
        if self._jobs_run:
            return self._jobs_run.popleft()
        return None

    def _worker_loop(self) -> None:
        thread_name = threading.current_thread().name
        logger.debug("Worker started", extra={"worker": thread_name})
        while True:
            with self._lock:
                while not self._stop_event.is_set():
                    job = self._pop_next_locked()
                    if job is not None:
                        break
                    self._cv.wait(timeout=self._poll_interval_s)
                else:
                    logger.debug("Worker stopping", extra={"worker": thread_name})
                    return
            logger.debug(
                "Job dequeued",
                extra={
                    "worker": thread_name,
                    "job_id": job.id,
                    "assessment_id": job.spec.assessment_id,
                    "type": job.spec.type,
                },
            )
            self._process_job(job)

    def _process_job(self, job: _Job) -> None:
        with self._lock:
            self._set_status(job.id, "running")
        t0 = time.perf_counter()
        try:
            result = self._execute(job)
            dur = time.perf_counter() - t0
            logger.info(
                "Job executed, posting callback",
                extra={
                    "job_id": job.id,
                    "assessment_id": job.spec.assessment_id,
                    "type": job.spec.type,
                    "duration_s": round(dur, 4),
                    "callback_host": self._callback_host(job.callback_url),
                },
            )
            resp = httpx.post(
                job.callback_url,
                json=result.model_dump(mode="json"),
                timeout=self._callback_timeout_s,
            )
            logger.info(
                "Callback response",
                extra={"job_id": job.id, "status_code": resp.status_code},
            )
            resp.raise_for_status()
            with self._lock:
                self._set_status(job.id, "completed")
            logger.info("Callback succeeded", extra={"job_id": job.id})
        except Exception:
            with self._lock:
                self._set_status(job.id, "failed")
            logger.exception(
                "Job failed",
                extra={
                    "job_id": job.id,
                    "assessment_id": job.spec.assessment_id,
                    "type": job.spec.type,
                },
            )

    def _callback_host(self, url: str) -> str:
        try:
            from urllib.parse import urlparse

            u = urlparse(url)
            # drop the final token path segment
            base_path = u.path.rsplit("/", 1)[0]
            return f"{u.scheme}://{u.netloc}{base_path}"
        except Exception:
            return "<redacted>"

    # ------- Shared staging and parsing -------

    def _write_submissions_csv(self, path: Path, raw_subs: list[RawSubmission]) -> None:
        qids: set[str] = set()
        for rs in raw_subs:
            qids.update(rs.raw_answer_map.keys())
        ordered_qids = natsorted(qids)

        logger.debug(
            "Staging submissions CSV",
            extra={"path": str(path), "rows": len(raw_subs), "columns": len(ordered_qids) + 1},
        )

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["student_id", *ordered_qids])
            writer.writeheader()
            for rs in raw_subs:
                row = {"student_id": rs.student_id}
                for qid in ordered_qids:
                    row[qid] = rs.raw_answer_map.get(qid, "")
                writer.writerow(row)

    def _parse_output_yaml(self, out_yaml: Path) -> list[GradedSubmission]:
        logger.debug("Parsing engine output", extra={"path": str(out_yaml)})
        items_raw = out_yaml.read_text(encoding="utf-8")
        items: list[Any] = yaml.safe_load(items_raw) or []
        return [GradedSubmission.model_validate(obj) for obj in items]

    # ------- Execution orchestration -------

    def _execute(self, job: _Job) -> GradingJobResult:
        spec = job.spec
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)
            submissions_csv = workdir / "submissions.csv"
            qset_yaml = workdir / "question_set.yaml"
            rubric_yaml = workdir / "rubric.yaml"
            out_yaml = workdir / "graded.yaml"

            logger.debug(
                "Staging inputs",
                extra={
                    "job_id": job.id,
                    "workdir": str(workdir),
                    "files": {
                        "submissions": str(submissions_csv),
                        "qset": str(qset_yaml),
                        "rubric": str(rubric_yaml),
                    },
                },
            )

            # Stage inputs
            self._write_submissions_csv(submissions_csv, spec.raw_submissions)
            qset_yaml.write_text(yaml.safe_dump(spec.question_set.model_dump()), encoding="utf-8")
            # Minimal rubric dump to avoid engine-internal fields
            rubric_yaml.write_text(
                yaml.safe_dump(model_dump_minimal(spec.rubric)), encoding="utf-8"
            )

            # Invoke engine (subclass-specific)
            t0 = time.perf_counter()
            self._invoke_engine(
                workdir=workdir,
                submissions_csv=submissions_csv,
                qset_yaml=qset_yaml,
                rubric_yaml=rubric_yaml,
                out_path=out_yaml,
            )
            dur = time.perf_counter() - t0
            logger.info(
                "Engine invocation finished",
                extra={
                    "job_id": job.id,
                    "duration_s": round(dur, 4),
                    "output_exists": out_yaml.exists(),
                },
            )

            if not out_yaml.exists():
                logger.error("Engine did not produce output", extra={"job_id": job.id})
                raise RuntimeError("Engine did not produce the expected output file")

            graded = self._parse_output_yaml(out_yaml)
            logger.info(
                "Parsed graded submissions",
                extra={"job_id": job.id, "count": len(graded)},
            )

            return GradingJobResult(
                assessment_id=spec.assessment_id,
                type=spec.type,
                graded_submissions=graded,
            )

    # ------- Abstract hook to implement in subclasses -------

    def _invoke_engine(
        self,
        *,
        workdir: Path,
        submissions_csv: Path,
        qset_yaml: Path,
        rubric_yaml: Path,
        out_path: Path,
    ) -> None:
        """
        Subclasses must implement this to run the gradeflow-engine and produce out_path.
        Should raise on failure. Must honor self._timeout_s.
        """
        raise NotImplementedError
