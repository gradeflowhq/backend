import yaml
import valkey
from fastapi import Request
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from gradeflow_backend.executors.exceptions import JobNotFoundError
from gradeflow_backend.executors.factory import get_executor
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.grading_jobs import GradingJobRepository
from gradeflow_backend.repositories.one_time_tokens import OneTimeTokenRepository
from gradeflow_backend.schemas.grading import (
    GradingJob,
    GradingJobResult,
    GradingJobSpec,
    JobStatusResponse,
)
from gradeflow_backend.services.exceptions import BadRequestError, NotFoundError
from gradeflow_backend.utils.jobs import build_callback_url, build_grading_job


class JobsService:
    def __init__(self, db: Session, valkey_client: valkey.Valkey) -> None:
        self.db = db
        self.assessments = AssessmentRepository(db, valkey_client)
        self.grading_jobs = GradingJobRepository(db)
        self.tokens = OneTimeTokenRepository(db)
        self.executor = get_executor()

    def _set_data(self, assessment_id: str, type: str, yaml_str: str | None) -> None:
        if type == "preview":
            self.assessments.set_preview_yaml(assessment_id, yaml_str)
        elif type == "run":
            self.assessments.set_submissions_yaml(assessment_id, yaml_str)
        else:
            raise BadRequestError("Unknown job type")

    def submit(self, spec: GradingJobSpec, request: Request) -> GradingJob:
        """
        Submit a grading job and persist the one-time callback token and job_id immediately.
        """
        try:
            # Validate assessment exists
            _ = self.assessments.get(spec.assessment_id)

            # Create one-time token and build callback URL
            tok = self.tokens.create()
            callback_url = build_callback_url(request, tok.token)

            # Commit token so that it is available for the executor callback
            self.db.commit()

            # Enqueue job
            job_id = self.executor.submit(spec, callback_url=callback_url)

            # Persist job_id
            self.grading_jobs.create(spec.assessment_id, spec.type, job_id)

            # Commit job_id
            self.db.commit()

            return build_grading_job(request, job_id)
        except Exception:
            self.db.rollback()
            raise

    def get_status(self, job_id: str) -> JobStatusResponse:
        try:
            return JobStatusResponse(job_id=job_id, status=self.executor.get_status(job_id))
        except JobNotFoundError as e:
            raise NotFoundError("Job not found") from e

    def on_callback(self, token: str, result: GradingJobResult) -> None:
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
        self.tokens.consume(token)

        # Assessment validation
        try:
            _ = self.assessments.get(result.assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        # Persist results
        payload = [gs.model_dump() for gs in result.submissions]
        yaml_str = yaml.safe_dump(payload)
        self._set_data(result.assessment_id, result.type, yaml_str)
