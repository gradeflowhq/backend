from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session
from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.repositories.memberships import MembershipRepository
from gradeflow_backend.repositories.users import UserRepository
from gradeflow_backend.schemas.memberships import (
    AddMemberRequest,
    MembershipResponse,
    SetRoleRequest,
)
from gradeflow_backend.schemas.users import AssessmentUsersResponse, UserResponse
from gradeflow_backend.services.exceptions import NotFoundError

router = APIRouter(prefix="/assessments/{assessment_id}/members", tags=["memberships"])


def get_membership_repo(db: Session = Depends(get_session)) -> MembershipRepository:
    return MembershipRepository(db)


def get_user_repo(db: Session = Depends(get_session)) -> UserRepository:
    return UserRepository(db)


@router.get("", response_model=AssessmentUsersResponse)
def list_members(
    assessment_id: str,
    memberships: MembershipRepository = Depends(get_membership_repo),
    _u: str = Depends(member_guard_factory()),
) -> AssessmentUsersResponse:
    # Fetch users and roles in a single query to avoid N+1
    members = memberships.list_assessment_members_with_roles(assessment_id)
    items = [
        UserResponse(id=user.id, email=user.email, name=user.name, role=role)
        for user, role in members
    ]
    return AssessmentUsersResponse(items=items)


@router.post("", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    assessment_id: str,
    req: AddMemberRequest,
    memberships: MembershipRepository = Depends(get_membership_repo),
    users: UserRepository = Depends(get_user_repo),
    _u: str = Depends(role_guard_factory("owner")),
) -> MembershipResponse:
    # Resolve user by email with basic normalization
    email = req.user_email.strip().lower()
    user = users.get_by_email(email)
    if user is None:
        raise NotFoundError("User not found")

    role = req.role or "viewer"
    memberships.add_member(user.id, assessment_id, role=role)
    return MembershipResponse(assessment_id=assessment_id, user_id=user.id, role=role)


@router.patch("/{user_id}", response_model=MembershipResponse)
def set_member_role(
    assessment_id: str,
    user_id: str,
    req: SetRoleRequest,
    memberships: MembershipRepository = Depends(get_membership_repo),
    _u: str = Depends(role_guard_factory("owner")),
) -> MembershipResponse:
    memberships.set_role(user_id, assessment_id, role=req.role)
    return MembershipResponse(assessment_id=assessment_id, user_id=user_id, role=req.role)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    assessment_id: str,
    user_id: str,
    memberships: MembershipRepository = Depends(get_membership_repo),
    _u: str = Depends(role_guard_factory("owner")),
) -> None:
    memberships.remove_member(user_id, assessment_id)
