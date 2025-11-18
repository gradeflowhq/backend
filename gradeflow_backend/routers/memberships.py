from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session
from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.memberships import MembershipRepository
from gradeflow_backend.repositories.users import UserRepository
from gradeflow_backend.schemas.memberships import (
    AddMemberRequest,
    MembershipResponse,
    SetRoleRequest,
)
from gradeflow_backend.schemas.users import AssessmentUsersResponse, UserResponse

router = APIRouter(prefix="/assessments/{assessment_id}/members", tags=["memberships"])


def get_membership_repo(db: Session = Depends(get_session)) -> MembershipRepository:
    return MembershipRepository(db)


def get_user_repo(db: Session = Depends(get_session)) -> UserRepository:
    return UserRepository(db)


def get_assessment_repo(db: Session = Depends(get_session)) -> AssessmentRepository:
    return AssessmentRepository(db)


@router.get("", response_model=AssessmentUsersResponse)
def list_members(
    assessment_id: str,
    memberships: MembershipRepository = Depends(get_membership_repo),
    _u: str = Depends(member_guard_factory()),
) -> AssessmentUsersResponse:
    users = memberships.list_assessment_users(assessment_id)
    return AssessmentUsersResponse(
        items=[UserResponse(id=u.id, email=u.email, name=u.name) for u in users]
    )


@router.post("", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    assessment_id: str,
    req: AddMemberRequest,
    memberships: MembershipRepository = Depends(get_membership_repo),
    _u: str = Depends(role_guard_factory("owner")),
) -> MembershipResponse:
    memberships.add_member(req.user_id, assessment_id, role=req.role or "viewer")
    return MembershipResponse(assessment_id=assessment_id, user_id=req.user_id)


@router.patch("/{user_id}", response_model=MembershipResponse)
def set_member_role(
    assessment_id: str,
    user_id: str,
    req: SetRoleRequest,
    memberships: MembershipRepository = Depends(get_membership_repo),
    _u: str = Depends(role_guard_factory("owner")),
) -> MembershipResponse:
    memberships.set_role(user_id, assessment_id, role=req.role)
    return MembershipResponse(assessment_id=assessment_id, user_id=user_id)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    assessment_id: str,
    user_id: str,
    memberships: MembershipRepository = Depends(get_membership_repo),
    _u: str = Depends(role_guard_factory("owner")),
) -> None:
    memberships.remove_member(user_id, assessment_id)
