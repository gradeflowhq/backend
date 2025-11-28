import logging
import subprocess
from pathlib import Path

from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.inmemory_base import (
    InMemoryBaseJobExecutor,
)
from gradeflow_backend.executors.registry import register

logger = logging.getLogger(__name__)


# Reuse the same CLI arguments as before
def _build_cli_command(
    submissions_csv: Path,
    qset_yaml: Path,
    rubric_yaml: Path,
    out_yaml: Path,
) -> list[str]:
    s = get_settings().executor
    return [
        s.engine_command,
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
        logger.info(
            "Invoking engine CLI",
            extra={"cmd": cmd, "timeout_s": self._timeout_s, "workdir": str(workdir)},
        )
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self._timeout_s,
            check=False,
        )
        logger.info(
            "Engine CLI completed",
            extra={"returncode": completed.returncode},
        )
        if completed.returncode != 0:
            # Emit stdout/stderr at debug to avoid noisy logs by default
            logger.debug("Engine stdout", extra={"stdout": completed.stdout[:4000]})
            logger.debug("Engine stderr", extra={"stderr": completed.stderr[:4000]})
            raise RuntimeError(f"CLI failed: {completed.stdout} {completed.stderr}")


@register("INMEMORY_SUBPROCESS")
def create_executor() -> InMemorySubprocessJobExecutor:
    s = get_settings().executor
    return InMemorySubprocessJobExecutor(
        timeout_s=s.job_timeout_s,
        poll_interval_s=s.job_poll_interval_s,
        num_workers=s.job_num_workers,
        callback_timeout_s=s.callback_timeout_s,
    )
