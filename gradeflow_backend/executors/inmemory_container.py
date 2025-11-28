import subprocess
from pathlib import Path

from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.inmemory_base import (
    DEFAULT_CALLBACK_TIMEOUT_S,
    DEFAULT_NUM_WORKERS,
    DEFAULT_POLL_INTERVAL_S,
    DEFAULT_TIMEOUT_S,
    InMemoryBaseJobExecutor,
)
from gradeflow_backend.executors.registry import register

DEFAULT_RUNTIME = "docker"
DEFAULT_IMAGE = "gradeflow-engine:latest"
DEFAULT_WORKDIR = "/workspace"  # inside the container


def _build_container_command(
    *,
    runtime: str,
    image: str,
    host_workdir: Path,
    in_container_workdir: str,
    submissions_csv: Path,
    qset_yaml: Path,
    rubric_yaml: Path,
    out_yaml: Path,
) -> list[str]:
    """
    Build a container run command compatible with docker/podman.
    Assumes runtime supports:
      - run --rm
      - -v host:container
      - -w working_dir
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
        "grade",
        "--submissions",
        str(Path(in_container_workdir) / submissions_csv.name),
        "--submissions-loader",
        "CSV",
        "--question-set",
        str(Path(in_container_workdir) / qset_yaml.name),
        "--question-set-loader",
        "YAML",
        "--rubric",
        str(Path(in_container_workdir) / rubric_yaml.name),
        "--rubric-loader",
        "YAML",
        "--saver",
        "YAML",
        "--out",
        str(Path(in_container_workdir) / out_yaml.name),
    ]


class InMemoryContainerJobExecutor(InMemoryBaseJobExecutor):
    def __init__(
        self,
        *,
        runtime: str = DEFAULT_RUNTIME,
        image: str = DEFAULT_IMAGE,
        container_workdir: str = DEFAULT_WORKDIR,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        callback_timeout_s: int = DEFAULT_CALLBACK_TIMEOUT_S,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        num_workers: int = DEFAULT_NUM_WORKERS,
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
        out_path: Path,
    ) -> None:
        cmd = _build_container_command(
            runtime=self._runtime,
            image=self._image,
            host_workdir=workdir,
            in_container_workdir=self._container_workdir,
            submissions_csv=submissions_csv,
            qset_yaml=qset_yaml,
            rubric_yaml=rubric_yaml,
            out_yaml=out_path,
        )
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self._timeout_s,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Container executor failed ({self._runtime}): "
                f"{completed.stdout} {completed.stderr}"
            )


@register("INMEMORY_CONTAINER")
def create_executor() -> InMemoryContainerJobExecutor:
    s = get_settings().executor
    return InMemoryContainerJobExecutor(
        runtime=s.job_container_runtime,
        image=s.job_container_image,
        container_workdir=s.job_container_workdir,
        callback_timeout_s=s.callback_timeout_s,
        timeout_s=s.job_timeout_s,
        poll_interval_s=s.job_poll_interval_s,
        num_workers=s.job_num_workers,
    )
