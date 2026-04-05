import builtins
from datetime import datetime

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.memberships import MembershipRepository
from gradeflow_backend.schemas.assessments import (
    AssessmentCreateRequest,
    AssessmentResponse,
    AssessmentUpdateRequest,
)
from gradeflow_backend.services.base import BaseService
from gradeflow_backend.utils.datetime import ensure_utc


def _effective_updated_at(a: Assessment) -> datetime:
    candidates: list[datetime | None] = [
        a.updated_at,
        a.question_set_updated_at,
        a.rubric_updated_at,
        a.source_updated_at,
        a.results_updated_at,
    ]
    return max(ensure_utc(dt) for dt in candidates if dt is not None)


def _build_response(a: Assessment) -> AssessmentResponse:
    return AssessmentResponse(
        id=a.id,
        name=a.name,
        description=a.description,
        created_at=a.created_at,
        updated_at=_effective_updated_at(a),
        question_set_updated_at=a.question_set_updated_at,
        rubric_updated_at=a.rubric_updated_at,
        source_updated_at=a.source_updated_at,
        results_updated_at=a.results_updated_at,
    )


class AssessmentService(BaseService):
    def __init__(self, repo: AssessmentRepository, memberships: MembershipRepository) -> None:
        super().__init__(repo)
        self.memberships = memberships

    def create(self, req: AssessmentCreateRequest, creator_user_id: str) -> AssessmentResponse:
        a = self.repo.create(req.name, req.description)
        self.memberships.add_member(creator_user_id, a.id, role="owner")
        return _build_response(a)

    def get(self, assessment_id: str) -> AssessmentResponse:
        return _build_response(self._get_or_404(assessment_id))

    def update(self, assessment_id: str, req: AssessmentUpdateRequest) -> AssessmentResponse:
        a = self._get_or_404(assessment_id)
        a = self.repo.update(a.id, req.name, req.description)
        return _build_response(a)

    def delete(self, assessment_id: str) -> None:
        self.repo.delete(self._get_or_404(assessment_id).id)

    def list_for_user(self, user_id: str) -> builtins.list[AssessmentResponse]:
        return [_build_response(a) for a in self.memberships.list_user_assessments(user_id)]
