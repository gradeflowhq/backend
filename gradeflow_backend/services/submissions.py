import yaml
from gradeflow_engine.core import load_submissions
from gradeflow_engine.submissions.models import RawSubmission
from sqlalchemy.exc import NoResultFound

from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.submissions import (
    SetSubmissionsByDataRequest,
    SetSubmissionsByModelRequest,
    SubmissionsResponse,
)
from gradeflow_backend.services.exceptions import NotFoundError


class SubmissionsService:
    def __init__(self, repo: AssessmentRepository) -> None:
        self.repo = repo

    def set_by_model(
        self, assessment_id: str, req: SetSubmissionsByModelRequest
    ) -> SubmissionsResponse:
        payload = [rs.model_dump() for rs in req.raw_submissions]
        try:
            self.repo.set_submissions_yaml(assessment_id, yaml.safe_dump(payload))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return SubmissionsResponse(raw_submissions=req.raw_submissions)

    def set_by_data(
        self, assessment_id: str, req: SetSubmissionsByDataRequest
    ) -> SubmissionsResponse:
        raw = load_submissions(req.data, loader_name=req.loader_name, **(req.loader_kwargs or {}))
        payload = [rs.model_dump() for rs in raw]
        try:
            self.repo.set_submissions_yaml(assessment_id, yaml.safe_dump(payload))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return SubmissionsResponse(raw_submissions=raw)

    def get(self, assessment_id: str) -> SubmissionsResponse:
        try:
            yaml_str = self.repo.get_submissions_yaml(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not yaml_str:
            return SubmissionsResponse(raw_submissions=[])
        items: list[dict[str, object]] = yaml.safe_load(yaml_str)
        raw = [RawSubmission.model_validate(obj) for obj in items]
        return SubmissionsResponse(raw_submissions=raw)

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.set_submissions_yaml(assessment_id, None)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
