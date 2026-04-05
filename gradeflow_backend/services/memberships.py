from gradeflow_backend.repositories.memberships import MembershipRepository
from gradeflow_backend.repositories.users import UserRepository
from gradeflow_backend.schemas.memberships import (
    AddMemberRequest,
    MembershipResponse,
    SetRoleRequest,
)
from gradeflow_backend.schemas.roles import Role
from gradeflow_backend.schemas.users import AssessmentUsersResponse, UserResponse
from gradeflow_backend.services.exceptions import NotFoundError


class MembershipService:
    """
    Encapsulates all membership business logic, keeping routers thin.
    """

    def __init__(
        self,
        memberships: MembershipRepository,
        users: UserRepository,
    ) -> None:
        self._memberships = memberships
        self._users = users

    def list_members(self, assessment_id: str) -> AssessmentUsersResponse:
        members = self._memberships.list_assessment_members_with_roles(assessment_id)
        items = [
            UserResponse(id=user.id, email=user.email, name=user.name, role=role)
            for user, role in members
        ]
        return AssessmentUsersResponse(items=items)

    def add_member(self, assessment_id: str, req: AddMemberRequest) -> MembershipResponse:
        email = req.user_email.strip().lower()
        user = self._users.get_by_email(email)
        if user is None:
            raise NotFoundError("User not found")
        role: Role = req.role or "viewer"
        self._memberships.add_member(user.id, assessment_id, role=role)
        return MembershipResponse(assessment_id=assessment_id, user_id=user.id, role=role)

    def set_role(self, assessment_id: str, user_id: str, req: SetRoleRequest) -> MembershipResponse:
        self._memberships.set_role(user_id, assessment_id, role=req.role)
        return MembershipResponse(assessment_id=assessment_id, user_id=user_id, role=req.role)

    def remove_member(self, assessment_id: str, user_id: str) -> None:
        self._memberships.remove_member(user_id, assessment_id)
