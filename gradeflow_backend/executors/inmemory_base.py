import importlib.resources as ir
import json
import logging
import tempfile
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from gradeflow_backend.executors.base import GradingJobExecutor, format_job_error
from gradeflow_backend.executors.exceptions import JobNotFoundError
from gradeflow_backend.schemas.grading import GradingJobSpec, JobStatus
from gradeflow_backend.utils.renderers import (
    render_point_columns_map,
    render_question_set_yaml,
    render_rubric_yaml_minimal,
    render_submissions_csv,
)

DEFAULT_CALLBACK_TIMEOUT_S = 10
DEFAULT_TIMEOUT_S = 300
DEFAULT_POLL_INTERVAL_S = 1
DEFAULT_NUM_WORKERS = 4

logger = logging.getLogger(__name__)


def _load_entrypoint_source() -> str:
    """Load the shared entrypoint.py source from package data."""
    entry = ir.files("gradeflow_backend.executors").joinpath("entrypoint.py")
    return entry.read_text(encoding="utf-8")


@dataclass(frozen=True)
class _Job:
    id: str
    spec: GradingJobSpec
    callback_url: str
    callback_secret: str


class InMemoryBaseJobExecutor(GradingJobExecutor):
    """
    Shared in-memory executor with:
      - preview/run prioritized queues
      - worker threads
      - filesystem staging of inputs/outputs
      - entrypoint-based callback delegation

    Subclasses must implement `_invoke_engine(...)` to run the shared entrypoint.py,
    passing GF_* environment variables (including the real callback URL). The
    entrypoint is responsible for invoking gradeflow-engine and posting the callback.
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
        self._errors: dict[str, str | None] = {}

        # Track cancelled job IDs
        self._cancelled: set[str] = set()

        # Concurrency primitives
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._cv = threading.Condition(self._lock)

        # Multiple worker threads
        self._workers: list[threading.Thread] = []
        self._started = False

    # ------- GradingJobExecutor API -------

    def submit(self, spec: GradingJobSpec, callback_url: str, callback_secret: str) -> str:
        self.start()
        job_id = f"job-{uuid.uuid4().hex}-{spec.type}"
        job = _Job(id=job_id, spec=spec, callback_url=callback_url, callback_secret=callback_secret)
        with self._lock:
            self._status[job_id] = "queued"
            self._errors[job_id] = None
            if spec.type == "preview":
                self._jobs_preview.append(job)
            else:
                self._jobs_run.append(job)
            self._cv.notify()
        return job_id

    def get_status(self, job_id: str) -> JobStatus:
        with self._lock:
            if job_id not in self._status:
                raise JobNotFoundError(f"Job not found: {job_id}")
            return self._status.get(job_id, "failed")

    def get_error(self, job_id: str) -> str | None:
        with self._lock:
            if job_id not in self._status:
                raise JobNotFoundError(f"Job not found: {job_id}")
            return self._errors.get(job_id)

    def cancel(self, job_id: str) -> None:
        with self._lock:
            if job_id not in self._status:
                raise JobNotFoundError(f"Job not found: {job_id}")
            status = self._status[job_id]
            if status in ("completed", "failed"):
                return
            self._cancelled.add(job_id)
            self._status[job_id] = "failed"
            self._errors[job_id] = "Job cancelled."
            # Remove from preview queue if queued
            self._jobs_preview = deque(j for j in self._jobs_preview if j.id != job_id)
            self._jobs_run = deque(j for j in self._jobs_run if j.id != job_id)

    def start(self) -> None:
        if self._started:
            return
        self._stop_event.clear()
        # Spawn N workers
        for i in range(self._num_workers):
            t = threading.Thread(target=self._worker_loop, name=f"GF-Worker-{i}", daemon=True)
            self._workers.append(t)
            t.start()
        self._started = True

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set()
            self._cv.notify_all()
        for t in self._workers:
            if t.is_alive():
                t.join(timeout=2)
        self._workers.clear()
        self._started = False

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
        while True:
            with self._lock:
                while not self._stop_event.is_set():
                    job = self._pop_next_locked()
                    if job is not None:
                        break
                    self._cv.wait(timeout=self._poll_interval_s)
                else:
                    return
            self._process_job(job)

    def _stage_inputs(
        self,
        *,
        workdir: Path,
        spec: GradingJobSpec,
    ) -> tuple[Path, Path, Path, Path, Path]:
        """
        Writes submissions.csv, question_set.yaml, rubric.yaml, entrypoint.py, and out path.
        Returns paths: (submissions_csv, qset_yaml, rubric_yaml, entrypoint_py, out_yaml)
        """
        submissions_csv = workdir / "submissions.csv"
        qset_yaml = workdir / "question_set.yaml"
        rubric_yaml = workdir / "rubric.yaml"
        entrypoint_py = workdir / "entrypoint.py"
        out_yaml = workdir / "graded.yaml"

        submissions_csv.write_text(render_submissions_csv(spec), encoding="utf-8", newline="")
        qset_yaml.write_text(render_question_set_yaml(spec), encoding="utf-8")
        rubric_yaml.write_text(render_rubric_yaml_minimal(spec), encoding="utf-8")
        entrypoint_py.write_text(_load_entrypoint_source(), encoding="utf-8")
        entrypoint_py.chmod(0o755)

        return submissions_csv, qset_yaml, rubric_yaml, entrypoint_py, out_yaml

    def _process_job(self, job: _Job) -> None:
        with self._lock:
            if job.id in self._cancelled:
                return
            self._set_status(job.id, "running")
        try:
            self._execute(job)
            with self._lock:
                if job.id not in self._cancelled:
                    self._set_status(job.id, "completed")
                    self._errors[job.id] = None
        except Exception as exc:
            with self._lock:
                self._set_status(job.id, "failed")
                self._errors[job.id] = format_job_error(exc)
            logger.exception("Job failed", extra={"job_id": job.id})

    # ------- Execution orchestration -------

    def _execute(self, job: _Job) -> None:
        spec = job.spec
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)

            # Stage inputs and entrypoint
            submissions_csv, qset_yaml, rubric_yaml, entrypoint_py, out_yaml = self._stage_inputs(
                workdir=workdir, spec=spec
            )

            # Invoke engine via entrypoint (which performs the callback)
            self._invoke_engine(
                workdir=workdir,
                submissions_csv=submissions_csv,
                qset_yaml=qset_yaml,
                rubric_yaml=rubric_yaml,
                entrypoint_py=entrypoint_py,
                out_path=out_yaml,
                callback_url=job.callback_url,
                callback_secret=job.callback_secret,
                assessment_id=spec.assessment_id,
                job_type=spec.type,
                point_columns_json=json.dumps(render_point_columns_map(spec)),
                remove_adjustments=spec.remove_adjustments,
                override_results=spec.override_results,
                grade_questions_without_rule=spec.grade_questions_without_rule,
            )

    # ------- Abstract hook to implement in subclasses -------

    def _invoke_engine(
        self,
        *,
        workdir: Path,
        submissions_csv: Path,
        qset_yaml: Path,
        rubric_yaml: Path,
        entrypoint_py: Path,
        out_path: Path,
        callback_url: str,
        callback_secret: str,
        assessment_id: str,
        job_type: str,  # "run" | "preview"
        point_columns_json: str = "{}",
        remove_adjustments: bool = False,
        override_results: bool = True,
        grade_questions_without_rule: bool = True,
    ) -> None:
        """
        Subclasses must implement this to run the shared entrypoint and produce out_path.
        Should raise on failure. Must honor self._timeout_s. Must pass GRADEFLOW_* envs.
        """
        raise NotImplementedError
