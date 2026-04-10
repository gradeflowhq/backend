import json
import logging
import uuid
from typing import Any, cast

import nomad.api.exceptions  # type: ignore[import-untyped]
from nomad import Nomad

from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.base import GradingJobExecutor, format_job_error
from gradeflow_backend.executors.exceptions import JobNotFoundError
from gradeflow_backend.executors.inmemory_base import _load_entrypoint_source
from gradeflow_backend.executors.registry import register
from gradeflow_backend.schemas.grading import GradingJobSpec, JobStatus
from gradeflow_backend.utils.renderers import (
    render_point_columns_map,
    render_question_set_yaml,
    render_rubric_yaml_minimal,
    render_submissions_csv,
)

logger = logging.getLogger(__name__)

DEFAULT_WORKDIR = "/workspace"
DEFAULT_IMAGE = "gradeflow-engine:latest"
DEFAULT_ENGINE_BIN = "gradeflow-engine"
DEFAULT_TASK_NAME = "gradeflow"
DEFAULT_GROUP_NAME = "gradeflow-group"
DEFAULT_PREVIEW_RUN_PRIORITY = 50
DEFAULT_GRADING_RUN_PRIORITY = 25
DEFAULT_RESTART_POLICY: dict[str, str | int] = {
    "attempts": 0,
    "interval": 30_000_000_000,
    "delay": 1_000_000_000,
    "mode": "fail",
}
DEFAULT_LOG_CONFIG: dict[str, int] = {
    "max_files": 5,
    "max_file_size": 10_000_000,
}
DEFAULT_DATACENTERS = ["dc1"]
DEFAULT_FILE_PERMS = "0644"
DEFAULT_SCRIPT_PERMS = "0755"
DEFAULT_DOCKER_DRIVER = "docker"


def _select_priority(job_type: str) -> int:
    normalized = job_type.strip().lower()
    if normalized in {"preview", "dry-run", "validate"}:
        return DEFAULT_PREVIEW_RUN_PRIORITY
    return DEFAULT_GRADING_RUN_PRIORITY


def _build_nomad_job(
    job_id: str,
    spec: GradingJobSpec,
    *,
    submissions_csv: str,
    question_set_yaml: str,
    rubric_yaml: str,
    entrypoint_py: str,
    callback_url: str,
    point_columns_json: str = "{}",
) -> dict[str, Any]:
    s = get_settings().executor
    image = s.container_image or DEFAULT_IMAGE
    workdir = s.container_workdir or DEFAULT_WORKDIR
    datacenters = s.nomad_datacenters or DEFAULT_DATACENTERS
    priority = _select_priority(spec.type)

    env: dict[str, str] = {
        "GRADEFLOW_ASSESSMENT_ID": spec.assessment_id,
        "GRADEFLOW_JOB_TYPE": spec.type,
        "GRADEFLOW_CALLBACK_URL": callback_url,
        "GRADEFLOW_ENGINE_BIN": DEFAULT_ENGINE_BIN,
        "GRADEFLOW_WORKDIR": workdir,
        "GRADEFLOW_SUBMISSIONS_PATH": f"{workdir}/submissions.csv",
        "GRADEFLOW_QSET_PATH": f"{workdir}/question_set.yaml",
        "GRADEFLOW_RUBRIC_PATH": f"{workdir}/rubric.yaml",
        "GRADEFLOW_OUT_PATH": f"{workdir}/graded.yaml",
        "GRADEFLOW_TIMEOUT_S": str(s.timeout_s),
        "GRADEFLOW_CALLBACK_TIMEOUT_S": str(s.callback_timeout_s),
        "GRADEFLOW_POINT_COLUMNS_JSON": point_columns_json,
        "GRADEFLOW_REMOVE_ADJUSTMENTS": str(spec.remove_adjustments).lower(),
    }

    templates: list[dict[str, str]] = [
        {
            "EmbeddedTmpl": submissions_csv,
            "DestPath": f"{workdir}/submissions.csv",
            "Perms": DEFAULT_FILE_PERMS,
        },
        {
            "EmbeddedTmpl": question_set_yaml,
            "DestPath": f"{workdir}/question_set.yaml",
            "Perms": DEFAULT_FILE_PERMS,
        },
        {
            "EmbeddedTmpl": rubric_yaml,
            "DestPath": f"{workdir}/rubric.yaml",
            "Perms": DEFAULT_FILE_PERMS,
        },
        {
            "EmbeddedTmpl": entrypoint_py,
            "DestPath": f"{workdir}/entrypoint.py",
            "Perms": DEFAULT_SCRIPT_PERMS,
        },
    ]

    task: dict[str, Any] = {
        "name": DEFAULT_TASK_NAME,
        "driver": DEFAULT_DOCKER_DRIVER,
        "config": {
            "image": image,
            "entrypoint": ["python", f"{workdir}/entrypoint.py"],
            "work_dir": workdir,
        },
        "env": env,
        "templates": templates,
        "resources": {
            "CPU": s.nomad_cpu,
            "MemoryMB": s.nomad_memory_mb,
        },
        "logs": DEFAULT_LOG_CONFIG,
        "restart_policy": DEFAULT_RESTART_POLICY,
    }

    group: dict[str, Any] = {"name": DEFAULT_GROUP_NAME, "count": 1, "tasks": [task]}

    job: dict[str, Any] = {
        "Job": {
            "ID": job_id,
            "Name": job_id,
            "Type": "batch",
            "Priority": priority,
            "Datacenters": datacenters,
            "TaskGroups": [group],
        }
    }
    if s.nomad_namespace:
        job["Job"]["Namespace"] = s.nomad_namespace

    return job


class NomadJobExecutor(GradingJobExecutor):
    def __init__(self) -> None:
        s = get_settings().executor
        host = s.nomad_host or "127.0.0.1"
        port = s.nomad_port
        token = s.nomad_token or None
        verify_tls = s.nomad_verify_tls
        timeout_s = s.timeout_s

        self._namespace = s.nomad_namespace or None
        self._nomad = Nomad(host=host, port=port, token=token, verify=verify_tls, timeout=timeout_s)

    def submit(self, spec: GradingJobSpec, callback_url: str) -> str:
        job_id = f"gf-{uuid.uuid4().hex}-{spec.type}"

        job = _build_nomad_job(
            job_id,
            spec,
            submissions_csv=render_submissions_csv(spec),
            question_set_yaml=render_question_set_yaml(spec),
            rubric_yaml=render_rubric_yaml_minimal(spec),
            entrypoint_py=_load_entrypoint_source(),
            callback_url=callback_url,
            point_columns_json=json.dumps(render_point_columns_map(spec)),
        )

        logger.info("Registering Nomad job", extra={"job_id": job_id, "namespace": self._namespace})

        jobs_api: Any = self._nomad.jobs
        if self._namespace:
            jobs_api.register_job(job, namespace=self._namespace)
        else:
            jobs_api.register_job(job)

        return job_id

    def get_status(self, job_id: str) -> JobStatus:
        try:
            job = cast(dict[str, Any], self._nomad.job.get_job(job_id, namespace=self._namespace))
        except nomad.api.exceptions.URLNotFoundNomadException as e:
            logger.error("Nomad job not found", extra={"job_id": job_id})
            raise JobNotFoundError(f"Job not found: {job_id}") from e
        status = cast(str, job["Status"])
        if status not in {"pending", "running", "dead"}:
            logger.warning(
                "Unexpected Nomad job status",
                extra={"job_id": job_id, "status": status},
            )
            return "failed"
        if status == "pending":
            return "queued"
        elif status == "running":
            return "running"

        allocations = cast(
            list[dict[str, Any]],
            self._nomad.job.get_allocations(job_id, namespace=self._namespace),
        )
        if not allocations:
            logger.warning("Nomad job dead with no allocations", extra={"job_id": job_id})
            return "failed"
        completed: bool = all(alloc["ClientStatus"] == "complete" for alloc in allocations)
        if completed:
            return "completed"
        return "failed"

    def get_error(self, job_id: str) -> str | None:
        try:
            allocations = cast(
                list[dict[str, Any]],
                self._nomad.job.get_allocations(job_id, namespace=self._namespace),
            )
        except nomad.api.exceptions.URLNotFoundNomadException as e:
            logger.error("Nomad job not found", extra={"job_id": job_id})
            raise JobNotFoundError(f"Job not found: {job_id}") from e

        messages: list[str] = []
        for allocation in allocations:
            if allocation.get("ClientStatus") == "complete":
                continue

            task_states = cast(dict[str, Any], allocation.get("TaskStates") or {})
            for task_name, task_state in task_states.items():
                events = cast(list[dict[str, Any]], task_state.get("Events") or [])
                for event in reversed(events):
                    message = (
                        event.get("DisplayMessage") or event.get("Message") or event.get("Type")
                    )
                    if message:
                        messages.append(f"{task_name}: {message}")
                        break

        if not messages:
            return None

        deduped_messages = list(dict.fromkeys(messages))
        return format_job_error("; ".join(deduped_messages))

    def start(self) -> None:
        pass

    def cancel(self, job_id: str) -> None:
        try:
            jobs_api: Any = self._nomad.jobs
            if self._namespace:
                jobs_api.deregister_job(job_id, namespace=self._namespace)
            else:
                jobs_api.deregister_job(job_id)
            logger.info("Cancelled Nomad job", extra={"job_id": job_id})
        except nomad.api.exceptions.URLNotFoundNomadException as e:
            from gradeflow_backend.executors.exceptions import JobNotFoundError

            raise JobNotFoundError(f"Job not found: {job_id}") from e

    def stop(self) -> None:
        pass


@register("NOMAD")
def create_executor() -> GradingJobExecutor:
    return NomadJobExecutor()
