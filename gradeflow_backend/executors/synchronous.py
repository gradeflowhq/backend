import logging
import time
import uuid

import httpx

from gradeflow_backend.config import get_settings
from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.executors.registry import register
from gradeflow_backend.schemas.grading import GradingJobResult, GradingJobSpec, JobStatus
from gradeflow_backend.services.exceptions import RubricValidationError

logger = logging.getLogger(__name__)


class SynchronousJobExecutor(GradingJobExecutor):
    def submit(self, spec: GradingJobSpec, callback_url: str) -> str:
        job_id = f"job-{uuid.uuid4().hex}-{spec.type}"
        logger.info(
            "Running synchronous job",
            extra={"job_id": job_id, "assessment_id": spec.assessment_id, "type": spec.type},
        )
        t0 = time.perf_counter()
        try:
            # Parse submissions
            submissions = spec.question_set.parse(spec.raw_submissions)

            # Validate rubric against question set
            errors = spec.rubric.validate_rubric(spec.question_set)
            if errors:
                raise RubricValidationError(errors)

            # Grade
            submissions = spec.rubric.grade(
                submissions, spec.question_set.question_map, strict=False
            )

            # Build result
            result = GradingJobResult(
                assessment_id=spec.assessment_id,
                type=spec.type,
                submissions=submissions,
                remove_adjustments=spec.remove_adjustments,
            )

            # Post callback
            timeout_s = get_settings().executor.callback_timeout_s
            logger.info("Posting callback", extra={"job_id": job_id, "timeout_s": timeout_s})
            resp = httpx.post(callback_url, json=result.model_dump(mode="json"), timeout=timeout_s)
            logger.info(
                "Callback response", extra={"job_id": job_id, "status_code": resp.status_code}
            )
            resp.raise_for_status()

        except Exception:
            logger.exception("Synchronous grading failed", extra={"job_id": job_id})
        finally:
            dur = time.perf_counter() - t0
            logger.info(
                "Synchronous job finished",
                extra={"job_id": job_id, "duration_s": round(dur, 4)},
            )

        return job_id

    def get_status(self, job_id: str) -> JobStatus:
        return "completed"

    def start(self) -> None:
        return

    def stop(self) -> None:
        return


@register("SYNCHRONOUS")
def create_synchronous_executor() -> GradingJobExecutor:
    return SynchronousJobExecutor()
