from sqlalchemy.exc import NoResultFound

from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.memberships import MembershipRepository
from gradeflow_backend.schemas.assessments import (
    AssessmentCreateRequest,
    AssessmentResponse,
    AssessmentUpdateRequest,
)
from gradeflow_backend.services.exceptions import NotFoundError


class AssessmentService:
    def __init__(self, repo: AssessmentRepository, memberships: MembershipRepository) -> None:
        self.repo = repo
        self.memberships = memberships

    def create(self, req: AssessmentCreateRequest, creator_user_id: str) -> AssessmentResponse:
        a = self.repo.create(req.id, req.name, req.description)
        # Assign creator as owner
        self.memberships.add_member(creator_user_id, a.id, role="owner")
        # Build response
        return AssessmentResponse(
            id=a.id,
            name=a.name,
            description=a.description,
            created_at=a.created_at.isoformat(),
            updated_at=a.updated_at.isoformat(),
        )

    def list(self) -> list[AssessmentResponse]:
        items = self.repo.list()
        return [
            AssessmentResponse(
                id=a.id,
                name=a.name,
                description=a.description,
                created_at=a.created_at.isoformat(),
                updated_at=a.updated_at.isoformat(),
            )
            for a in items
        ]

    def get(self, assessment_id: str) -> AssessmentResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return AssessmentResponse(
            id=a.id,
            name=a.name,
            description=a.description,
            created_at=a.created_at.isoformat(),
            updated_at=a.updated_at.isoformat(),
        )

    def update(self, assessment_id: str, req: AssessmentUpdateRequest) -> AssessmentResponse:
        try:
            a = self.repo.update(assessment_id, req.name, req.description)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return AssessmentResponse(
            id=a.id,
            name=a.name,
            description=a.description,
            created_at=a.created_at.isoformat(),
            updated_at=a.updated_at.isoformat(),
        )

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.delete(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
