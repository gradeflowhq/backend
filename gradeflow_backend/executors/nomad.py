import json
import logging
from typing import Any, cast

import nomad.api.exceptions  # type: ignore[import-untyped]
from nomad import Nomad

from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.base import GradingJobExecutor, format_job_error
from gradeflow_backend.executors.env import build_gradeflow_env
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
    "Attempts": 0,
    "Interval": 30_000_000_000,
    "Delay": 1_000_000_000,
    "Mode": "fail",
}
DEFAULT_RESCHEDULE_POLICY: dict[str, bool | int] = {
    "Attempts": 0,
    "Unlimited": False,
}
DEFAULT_LOG_CONFIG: dict[str, int] = {
    "MaxFiles": 5,
    "MaxFileSizeMB": 10,
}
DEFAULT_DATACENTERS = ["dc1"]
DEFAULT_FILE_PERMS = "0644"
DEFAULT_SCRIPT_PERMS = "0755"
DEFAULT_DOCKER_DRIVER = "docker"
TERMINATED_EVENT_TYPE = "Terminated"


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
    callback_secret: str,
    point_columns_json: str = "{}",
    metadata_json: str = "{}",
) -> dict[str, Any]:
    s = get_settings().executor
    image = s.container_image or DEFAULT_IMAGE
    workdir = s.container_workdir or DEFAULT_WORKDIR
    datacenters = s.nomad_datacenters or DEFAULT_DATACENTERS
    priority = _select_priority(spec.type)

    env = build_gradeflow_env(
        assessment_id=spec.assessment_id,
        job_id=job_id,
        job_type=spec.type,
        callback_url=callback_url,
        callback_secret=callback_secret,
        engine_bin=s.engine_command or DEFAULT_ENGINE_BIN,
        workdir=workdir,
        submissions_path=f"{workdir}/submissions.csv",
        qset_path=f"{workdir}/question_set.yaml",
        rubric_path=f"{workdir}/rubric.yaml",
        out_path=f"{workdir}/graded.json",
        timeout_s=s.timeout_s,
        callback_timeout_s=s.callback_timeout_s,
        point_columns_json=point_columns_json,
        metadata_json=metadata_json,
        remove_adjustments=spec.remove_adjustments,
        override_results=spec.override_results,
        grade_questions_without_rule=spec.grade_questions_without_rule,
        rubric_grading_parallel_jobs=spec.rubric_grading_parallel_jobs,
        rubric_grading_parallel_mode=spec.rubric_grading_parallel_mode,
    )

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
        "Name": DEFAULT_TASK_NAME,
        "Driver": DEFAULT_DOCKER_DRIVER,
        "Config": {
            "image": image,
            "entrypoint": ["python", f"{workdir}/entrypoint.py"],
            "work_dir": workdir,
        },
        "Env": env,
        "Templates": templates,
        "Resources": {
            "CPU": s.nomad_cpu,
            "MemoryMB": s.nomad_memory_mb,
        },
        "LogConfig": DEFAULT_LOG_CONFIG,
        "RestartPolicy": DEFAULT_RESTART_POLICY,
    }

    group: dict[str, Any] = {
        "Name": DEFAULT_GROUP_NAME,
        "Count": 1,
        "Tasks": [task],
        "ReschedulePolicy": DEFAULT_RESCHEDULE_POLICY,
    }

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


def _latest_event_message(
    events: list[dict[str, Any]],
    *,
    event_type: str | None = None,
) -> str | None:
    return next(
        (
            event["DisplayMessage"]
            for event in reversed(events)
            if (event_type is None or event["Type"] == event_type) and event["DisplayMessage"]
        ),
        None,
    )


def _task_failure_message(events: list[dict[str, Any]]) -> str | None:
    return _latest_event_message(
        events,
        event_type=TERMINATED_EVENT_TYPE,
    ) or _latest_event_message(events)


class NomadJobExecutor(GradingJobExecutor):
    def __init__(self) -> None:
        s = get_settings().executor
        host = s.nomad_host or "127.0.0.1"
        port = s.nomad_port
        token = s.nomad_token or None
        namespace = s.nomad_namespace or None
        verify_tls = s.nomad_verify_tls
        timeout_s = s.timeout_s

        self._nomad = Nomad(
            host=host,
            port=port,
            token=token,
            namespace=namespace,
            verify=verify_tls,
            timeout=timeout_s,
        )

    def submit(
        self,
        job_id: str,
        spec: GradingJobSpec,
        callback_url: str,
        callback_secret: str,
    ) -> None:
        job = _build_nomad_job(
            job_id,
            spec,
            submissions_csv=render_submissions_csv(spec),
            question_set_yaml=render_question_set_yaml(spec),
            rubric_yaml=render_rubric_yaml_minimal(spec),
            entrypoint_py=_load_entrypoint_source(),
            callback_url=callback_url,
            callback_secret=callback_secret,
            point_columns_json=json.dumps(render_point_columns_map(spec)),
            metadata_json=json.dumps(spec.metadata),
        )

        logger.info("Registering Nomad job", extra={"job_id": job_id})

        self._nomad.jobs.register_job(job)

    def get_status(self, job_id: str) -> JobStatus:
        try:
            job = cast(dict[str, Any], self._nomad.job.get_job(job_id))
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
            self._nomad.job.get_allocations(job_id),
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
                self._nomad.job.get_allocations(job_id),
            )
        except nomad.api.exceptions.URLNotFoundNomadException as e:
            logger.error("Nomad job not found", extra={"job_id": job_id})
            raise JobNotFoundError(f"Job not found: {job_id}") from e

        messages: list[str] = []
        for allocation in allocations:
            if allocation.get("ClientStatus") == "complete":
                continue

            task_states = cast(dict[str, Any], allocation.get("TaskStates") or {})
            for _, task_state in task_states.items():
                events = cast(list[dict[str, Any]], task_state.get("Events") or [])
                message = _task_failure_message(events)
                if message:
                    messages.append(message)

        if not messages:
            return None

        deduped_messages = list(dict.fromkeys(messages))
        return format_job_error("; ".join(deduped_messages))

    def start(self) -> None:
        pass

    def cancel(self, job_id: str) -> None:
        try:
            self._nomad.job.deregister_job(job_id)
            logger.info("Cancelled Nomad job", extra={"job_id": job_id})
        except nomad.api.exceptions.URLNotFoundNomadException as e:
            from gradeflow_backend.executors.exceptions import JobNotFoundError

            raise JobNotFoundError(f"Job not found: {job_id}") from e

    def stop(self) -> None:
        pass


@register("NOMAD")
def create_executor() -> GradingJobExecutor:
    return NomadJobExecutor()
