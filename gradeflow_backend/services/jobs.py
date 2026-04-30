import logging
from typing import TypeVar

import valkey
import yaml
from fastapi import Request
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.executors.exceptions import JobNotFoundError
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.grading_jobs import GradingJobRepository
from gradeflow_backend.repositories.one_time_tokens import OneTimeTokenRepository
from gradeflow_backend.repositories.submissions import SubmissionRepository
from gradeflow_backend.schemas.grading import (
    GradingJob,
    GradingJobResult,
    GradingJobSpec,
    JobStatusResponse,
)
from gradeflow_backend.services.exceptions import (
    BadRequestError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from gradeflow_backend.utils.callback_signing import verify_callback_signature
from gradeflow_backend.utils.jobs import build_callback_url, build_grading_job

logger = logging.getLogger(__name__)

T = TypeVar("T")


class JobsService:
    def __init__(
        self,
        db: Session,
        valkey_client: valkey.Valkey,
        executor: GradingJobExecutor,
    ) -> None:
        self.db = db
        self.assessments = AssessmentRepository(db, valkey_client)
        self.grading_jobs = GradingJobRepository(db)
        self.tokens = OneTimeTokenRepository(db)
        self.submissions = SubmissionRepository(db)
        self.executor = executor

    def _set_data(self, assessment_id: str, type: str, result: GradingJobResult) -> None:
        if type == "preview":
            payload = [submission.model_dump() for submission in result.submissions]
            yaml_str = yaml.safe_dump(payload)
            self.assessments.set_preview_yaml(assessment_id, yaml_str)
        elif type == "run":
            self.submissions.bulk_upsert(
                assessment_id,
                result.submissions,
                remove_adjustments=result.remove_adjustments,
            )
            self.assessments.stamp_results_updated_at(result.assessment_id)
        else:
            raise BadRequestError("Unknown job type")

    def submit(self, spec: GradingJobSpec, request: Request) -> GradingJob:
        self.assessments.get(spec.assessment_id)

        # 1. Create token on the request session
        tok = self.tokens.create()
        callback_url = build_callback_url(request, tok.token)

        # 2. Commit token so the callback endpoint can see it.
        #    If anything fails after this, the token is orphaned but harmless.
        self.db.commit()

        # 3. Submit to executor (may trigger synchronous callback)
        try:
            job_id = self.executor.submit(
                spec,
                callback_url=callback_url,
                callback_secret=tok.secret,
            )
        except Exception as e:
            logger.exception(
                "Executor failed to submit grading job",
                extra={"assessment_id": spec.assessment_id, "job_type": spec.type},
            )
            raise ServiceUnavailableError(
                "Unable to start grading job. The grading executor is unavailable "
                "or failed to accept the job."
            ) from e

        # 4. Persist job record on the same session.
        #    get_session() commits this on success, rolls back on failure.
        self.grading_jobs.create(spec.assessment_id, spec.type, job_id)

        return build_grading_job(request, job_id)

    def get_status(self, job_id: str) -> JobStatusResponse:
        try:
            status = self.executor.get_status(job_id)
            error = self.executor.get_error(job_id) if status == "failed" else None
            return JobStatusResponse(job_id=job_id, status=status, error=error)
        except JobNotFoundError as e:
            raise NotFoundError("Job not found") from e
        except Exception as e:
            logger.exception("Executor failed to read job status", extra={"job_id": job_id})
            raise ServiceUnavailableError(
                "Unable to read grading job status. The grading executor is unavailable "
                "or returned an unexpected response."
            ) from e

    def cancel_job(self, job_id: str) -> None:
        """Cancel a running or queued job by job_id."""
        try:
            self.executor.cancel(job_id)
        except JobNotFoundError as e:
            raise NotFoundError("Job not found") from e
        except Exception as e:
            logger.exception("Executor failed to cancel job", extra={"job_id": job_id})
            raise ServiceUnavailableError(
                "Unable to cancel grading job. The grading executor is unavailable "
                "or failed to cancel the job."
            ) from e

    def on_callback(
        self,
        token: str,
        result: GradingJobResult,
        *,
        payload: bytes,
        signature: str | None,
    ) -> None:
        """
        Handle executor callback:
        - Validate and consume one-time token
        - Validate assessment
        - Persist graded results (YAML)
        """
        # Token validation
        try:
            tok = self.tokens.get(token)
        except NoResultFound as e:
            raise NotFoundError("Token not found") from e
        if not tok.is_valid():
            raise BadRequestError("Token already used or revoked")
        if not verify_callback_signature(tok.secret, payload, signature):
            raise UnauthorizedError("Invalid callback signature")
        self.tokens.consume(token)

        # Assessment validation
        try:
            self.assessments.get(result.assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        # Persist results
        self._set_data(result.assessment_id, result.type, result)
