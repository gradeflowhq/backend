import logging
import os
import subprocess
import sys
from pathlib import Path

from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.executors.env import build_gradeflow_env
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
        callback_secret: str,
        assessment_id: str,
        job_id: str,
        job_type: str,
        point_columns_json: str = "{}",
        remove_adjustments: bool = False,
        override_results: bool = True,
        grade_questions_without_rule: bool = True,
    ) -> None:
        """
        Invoke the shared entrypoint in a local Python subprocess, passing GRADEFLOW_* env vars.
        """
        s = get_settings().executor
        engine_bin = s.engine_command

        env = {
            **os.environ,
            **build_gradeflow_env(
                assessment_id=assessment_id,
                job_id=job_id,
                job_type=job_type,
                callback_url=callback_url,
                callback_secret=callback_secret,
                engine_bin=engine_bin,
                workdir=workdir,
                submissions_path=submissions_csv,
                qset_path=qset_yaml,
                rubric_path=rubric_yaml,
                out_path=out_path,
                timeout_s=self._timeout_s,
                callback_timeout_s=self._callback_timeout_s,
                point_columns_json=point_columns_json,
                remove_adjustments=remove_adjustments,
                override_results=override_results,
                grade_questions_without_rule=grade_questions_without_rule,
            ),
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
