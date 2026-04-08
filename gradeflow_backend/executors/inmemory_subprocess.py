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
        point_columns_json: str = "{}",
        remove_adjustments: bool = False,
    ) -> None:
        """
        Invoke the shared entrypoint in a local Python subprocess, passing GRADEFLOW_* env vars.
        """
        s = get_settings().executor
        engine_bin = s.engine_command

        env = {
            **os.environ,
            # identity and callback
            "GRADEFLOW_ASSESSMENT_ID": assessment_id,
            "GRADEFLOW_JOB_TYPE": job_type,
            "GRADEFLOW_CALLBACK_URL": callback_url,
            # execution and timeouts
            "GRADEFLOW_WORKDIR": str(workdir),
            "GRADEFLOW_TIMEOUT_S": str(self._timeout_s),
            "GRADEFLOW_CALLBACK_TIMEOUT_S": str(self._callback_timeout_s),
            # explicit paths to avoid drift
            "GRADEFLOW_ENGINE_BIN": engine_bin,
            "GRADEFLOW_SUBMISSIONS_PATH": str(submissions_csv),
            "GRADEFLOW_QSET_PATH": str(qset_yaml),
            "GRADEFLOW_RUBRIC_PATH": str(rubric_yaml),
            "GRADEFLOW_OUT_PATH": str(out_path),
            "GRADEFLOW_POINT_COLUMNS_JSON": point_columns_json,
            "GRADEFLOW_REMOVE_ADJUSTMENTS": str(remove_adjustments).lower(),
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
