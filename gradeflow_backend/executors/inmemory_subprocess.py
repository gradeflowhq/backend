import os
import subprocess
from pathlib import Path

from gradeflow_backend.executors.inmemory_base import (
    DEFAULT_NUM_WORKERS,
    DEFAULT_POLL_INTERVAL_S,
    GRADEFLOW_ENGINE_CMD,
    REQUEST_TIMEOUT_S,
    InMemoryBaseJobExecutor,
)
from gradeflow_backend.executors.registry import register


# Reuse the same CLI arguments as before
def _build_cli_command(
    submissions_csv: Path,
    qset_yaml: Path,
    rubric_yaml: Path,
    out_yaml: Path,
) -> list[str]:
    return [
        GRADEFLOW_ENGINE_CMD,
        "grade",
        "--submissions",
        str(submissions_csv),
        "--submissions-loader",
        "CSV",
        "--question-set",
        str(qset_yaml),
        "--question-set-loader",
        "YAML",
        "--rubric",
        str(rubric_yaml),
        "--rubric-loader",
        "YAML",
        "--saver",
        "YAML",
        "--out",
        str(out_yaml),
    ]


class InMemorySubprocessJobExecutor(InMemoryBaseJobExecutor):
    def _invoke_engine(
        self,
        *,
        workdir: Path,
        submissions_csv: Path,
        qset_yaml: Path,
        rubric_yaml: Path,
        out_path: Path,
    ) -> None:
        cmd = _build_cli_command(submissions_csv, qset_yaml, rubric_yaml, out_path)
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self._timeout_s,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"CLI failed: {completed.stdout} {completed.stderr}")


@register("INMEMORY_SUBPROCESS")
def create_executor() -> InMemorySubprocessJobExecutor:
    # Environment overrides
    timeout_s = int(os.getenv("JOB_TIMEOUT_S", REQUEST_TIMEOUT_S))
    poll_interval_s = float(os.getenv("JOB_POLL_INTERVAL_S", DEFAULT_POLL_INTERVAL_S))
    num_workers = int(os.getenv("JOB_NUM_WORKERS", DEFAULT_NUM_WORKERS))
    return InMemorySubprocessJobExecutor(
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
        num_workers=num_workers,
    )
