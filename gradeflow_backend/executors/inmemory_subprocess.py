import logging
import os
import subprocess
import sys
from pathlib import Path

from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.executors.inmemory_base import InMemoryBaseJobExecutor
from gradeflow_backend.executors.registry import register

logger = logging.getLogger(__name__)


class InMemorySubprocessJobExecutor(InMemoryBaseJobExecutor):
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
        assessment_id: str,
        job_type: str,
    ) -> None:
        """
        Invoke the shared entrypoint in a local Python subprocess, passing GF_* env vars.
        """
        s = get_settings().executor
        engine_bin = s.engine_command

        env = {
            **os.environ,
            # identity and callback
            "GF_ASSESSMENT_ID": assessment_id,
            "GF_JOB_TYPE": job_type,
            "GF_CALLBACK_URL": callback_url,
            # execution and timeouts
            "GF_WORKDIR": str(workdir),
            "GF_TIMEOUT_S": str(self._timeout_s),
            "GF_CALLBACK_TIMEOUT_S": str(self._callback_timeout_s),
            # explicit paths to avoid drift
            "GF_ENGINE_BIN": engine_bin,
            "GF_SUBMISSIONS_PATH": str(submissions_csv),
            "GF_QSET_PATH": str(qset_yaml),
            "GF_RUBRIC_PATH": str(rubric_yaml),
            "GF_OUT_PATH": str(out_path),
        }

        logger.info(
            "Invoking engine via entrypoint (subprocess)",
            extra={
                "workdir": str(workdir),
                "timeout_s": self._timeout_s,
                "entrypoint": str(entrypoint_py),
                "callback": callback_url,
            },
        )

        completed = subprocess.run(
            [sys.executable, str(entrypoint_py)],
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            timeout=self._timeout_s,
            check=False,
        )
        logger.info("Entrypoint completed", extra={"returncode": completed.returncode})
        if completed.returncode != 0:
            logger.debug("Entrypoint stdout", extra={"stdout": completed.stdout[:4000]})
            logger.debug("Entrypoint stderr", extra={"stderr": completed.stderr[:4000]})
            raise RuntimeError(f"Entrypoint failed: {completed.stdout} {completed.stderr}")


@register("INMEMORY_SUBPROCESS")
def create_executor() -> GradingJobExecutor:
    s = get_settings().executor
    return InMemorySubprocessJobExecutor(
        timeout_s=s.timeout_s,
        poll_interval_s=s.poll_interval_s,
        num_workers=s.num_workers,
        callback_timeout_s=s.callback_timeout_s,
    )
