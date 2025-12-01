import importlib.resources as ir
import logging
import uuid
from typing import Any, cast

from nomad import Nomad  # type: ignore[import-untyped]

from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.executors.registry import register
from gradeflow_backend.schemas.grading import GradingJobSpec, JobStatus
from gradeflow_backend.utils.renderers import (
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


def _load_entrypoint_source() -> str:
    entry = ir.files("gradeflow_backend.executors").joinpath("entrypoint.py")
    return entry.read_text(encoding="utf-8")


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
) -> dict[str, Any]:
    s = get_settings().executor
    image = s.container_image or DEFAULT_IMAGE
    workdir = s.container_workdir or DEFAULT_WORKDIR
    datacenters = s.nomad_datacenters or DEFAULT_DATACENTERS
    priority = _select_priority(spec.type)

    env: dict[str, str] = {
        "GF_ASSESSMENT_ID": spec.assessment_id,
        "GF_JOB_TYPE": spec.type,
        "GF_CALLBACK_URL": callback_url,
        "GF_ENGINE_BIN": DEFAULT_ENGINE_BIN,
        "GF_WORKDIR": workdir,
        "GF_SUBMISSIONS_PATH": f"{workdir}/submissions.csv",
        "GF_QSET_PATH": f"{workdir}/question_set.yaml",
        "GF_RUBRIC_PATH": f"{workdir}/rubric.yaml",
        "GF_OUT_PATH": f"{workdir}/graded.yaml",
        "GF_TIMEOUT_S": str(s.timeout_s),
        "GF_CALLBACK_TIMEOUT_S": str(s.callback_timeout_s),
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
        )

        logger.info("Registering Nomad job", extra={"job_id": job_id, "namespace": self._namespace})

        jobs_api: Any = self._nomad.jobs
        if self._namespace:
            jobs_api.register_job(job, namespace=self._namespace)
        else:
            jobs_api.register_job(job)

        return job_id

    def get_status(self, job_id: str) -> JobStatus:
        job = cast(dict[str, Any], self._nomad.job.get_job(job_id, namespace=self._namespace))
        status = cast(str, job["Status"])
        assert status in {"pending", "running", "dead"}, f"Unknown Nomad job status: {status}"
        if status == "pending":
            return "queued"
        elif status == "running":
            return "running"

        allocations = cast(
            list[dict[str, Any]],
            self._nomad.job.get_allocations(job_id, namespace=self._namespace),
        )
        completed: bool = all(alloc["ClientStatus"] == "complete" for alloc in allocations)
        if completed:
            return "completed"
        return "failed"

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


@register("NOMAD")
def create_executor() -> GradingJobExecutor:
    return NomadJobExecutor()
