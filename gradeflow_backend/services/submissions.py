import yaml
from gradeflow_engine.core import load_raw_submissions_via_adapter
from gradeflow_engine.submissions.models import RawSubmission
from sqlalchemy.exc import NoResultFound

from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.submissions import (
    ImportSubmissionsRequest,
    SetSubmissionsByModelRequest,
    SubmissionsResponse,
)
from gradeflow_backend.services.exceptions import NotFoundError
from gradeflow_backend.utils.io import source_from_data


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

    def set_by_adapter(
        self, assessment_id: str, req: ImportSubmissionsRequest
    ) -> SubmissionsResponse:
        src = source_from_data(req.data)
        raw = load_raw_submissions_via_adapter(
            src,
            adapter_name=req.adapter.name,
            adapter_kwargs=req.adapter.model_dump(exclude={"name"}),
        )
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
        items: list[dict[str, object]] = yaml.safe_load(yaml_str) or []
        raw = [RawSubmission.model_validate(obj) for obj in items]
        return SubmissionsResponse(raw_submissions=raw)

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.set_submissions_yaml(assessment_id, None)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
