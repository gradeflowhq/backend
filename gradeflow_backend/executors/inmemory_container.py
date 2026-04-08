import logging
import subprocess
from pathlib import Path

from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.executors.inmemory_base import InMemoryBaseJobExecutor
from gradeflow_backend.executors.registry import register

logger = logging.getLogger(__name__)

DEFAULT_RUNTIME = "docker"
DEFAULT_IMAGE = "gradeflow-engine:latest"
DEFAULT_WORKDIR = "/workspace"  # inside the container


def _build_container_command(
    *,
    runtime: str,
    image: str,
    host_workdir: Path,
    in_container_workdir: str,
) -> list[str]:
    """
    Build a container run command compatible with docker/podman.
    Mounts host workdir into the container and runs the shared entrypoint.py.
    """
    return [
        runtime,
        "run",
        "--rm",
        "-v",
        f"{host_workdir}:{in_container_workdir}",
        "-w",
        in_container_workdir,
        image,
        "python",
        f"{in_container_workdir}/entrypoint.py",
    ]


class InMemoryContainerJobExecutor(InMemoryBaseJobExecutor):
    def __init__(
        self,
        *,
        runtime: str = DEFAULT_RUNTIME,
        image: str = DEFAULT_IMAGE,
        container_workdir: str = DEFAULT_WORKDIR,
        timeout_s: int = 300,
        callback_timeout_s: int = 10,
        poll_interval_s: float = 1.0,
        num_workers: int = 4,
    ) -> None:
        super().__init__(
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
            num_workers=num_workers,
            callback_timeout_s=callback_timeout_s,
        )
        self._runtime = runtime
        self._image = image
        self._container_workdir = container_workdir

    def _invoke_engine(
        self,
        *,
        workdir: Path,
        submissions_csv: Path,
        qset_yaml: Path,
        rubric_yaml: Path,
        entrypoint_py: Path,  # staged on host; container reads mounted copy
        out_path: Path,
        callback_url: str,
        assessment_id: str,
        job_type: str,
        point_columns_json: str = "{}",
        remove_adjustments: bool = False,
    ) -> None:
        """
        Invoke the shared entrypoint inside a container, injecting GRADEFLOW_* env vars.
        """
        s = get_settings().executor
        engine_bin = s.engine_command  # e.g., "gradeflow-engine"

        cmd = _build_container_command(
            runtime=self._runtime,
            image=self._image,
            host_workdir=workdir,
            in_container_workdir=self._container_workdir,
        )

        # Inject environment via -e flags
        env_flags = [
            "-e",
            f"GRADEFLOW_ASSESSMENT_ID={assessment_id}",
            "-e",
            f"GRADEFLOW_JOB_TYPE={job_type}",
            "-e",
            f"GRADEFLOW_WORKDIR={self._container_workdir}",
            "-e",
            f"GRADEFLOW_CALLBACK_URL={callback_url}",
            "-e",
            f"GRADEFLOW_TIMEOUT_S={self._timeout_s}",
            "-e",
            f"GRADEFLOW_CALLBACK_TIMEOUT_S={self._callback_timeout_s}",
            "-e",
            f"GRADEFLOW_ENGINE_BIN={engine_bin}",
            "-e",
            f"GRADEFLOW_SUBMISSIONS_PATH={self._container_workdir}/submissions.csv",
            "-e",
            f"GRADEFLOW_QSET_PATH={self._container_workdir}/question_set.yaml",
            "-e",
            f"GRADEFLOW_RUBRIC_PATH={self._container_workdir}/rubric.yaml",
            "-e",
            f"GRADEFLOW_OUT_PATH={self._container_workdir}/graded.yaml",
            "-e",
            f"GRADEFLOW_POINT_COLUMNS_JSON={point_columns_json}",
            "-e",
            f"GRADEFLOW_REMOVE_ADJUSTMENTS={str(remove_adjustments).lower()}",
        ]
        # Insert env flags after 'run'
        try:
            run_idx = cmd.index("run")
            cmd = cmd[: run_idx + 1] + env_flags + cmd[run_idx + 1 :]
        except ValueError:
            cmd = cmd + env_flags

        logger.info(
            "Invoking engine in container via entrypoint",
            extra={
                "runtime": self._runtime,
                "image": self._image,
                "timeout_s": self._timeout_s,
                "cmd": cmd,
            },
        )
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self._timeout_s,
            check=False,
        )
        logger.info("Container run completed", extra={"returncode": completed.returncode})
        if completed.returncode != 0:
            logger.debug("Container stdout", extra={"stdout": completed.stdout[:4000]})
            logger.debug("Container stderr", extra={"stderr": completed.stderr[:4000]})
            raise RuntimeError(
                f"Container executor failed ({self._runtime}): "
                f"{completed.stdout} {completed.stderr}"
            )


@register("INMEMORY_CONTAINER")
def create_executor() -> GradingJobExecutor:
    s = get_settings().executor
    return InMemoryContainerJobExecutor(
        runtime=s.container_runtime,
        image=s.container_image,
        container_workdir=s.container_workdir,
        timeout_s=s.timeout_s,
        callback_timeout_s=s.callback_timeout_s,
        poll_interval_s=s.poll_interval_s,
        num_workers=s.num_workers,
    )
