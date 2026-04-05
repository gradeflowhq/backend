from fastapi import APIRouter, Depends, status

from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.dependencies.services import get_membership_service
from gradeflow_backend.schemas.memberships import (
    AddMemberRequest,
    MembershipResponse,
    SetRoleRequest,
)
from gradeflow_backend.schemas.users import AssessmentUsersResponse
from gradeflow_backend.services.memberships import MembershipService

router = APIRouter(prefix="/assessments/{assessment_id}/members", tags=["memberships"])


@router.get("", response_model=AssessmentUsersResponse)
def list_members(
    assessment_id: str,
    svc: MembershipService = Depends(get_membership_service),
    _u: str = Depends(member_guard_factory()),
) -> AssessmentUsersResponse:
    return svc.list_members(assessment_id)


@router.post("", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    assessment_id: str,
    req: AddMemberRequest,
    svc: MembershipService = Depends(get_membership_service),
    _u: str = Depends(role_guard_factory("owner")),
) -> MembershipResponse:
    return svc.add_member(assessment_id, req)


@router.patch("/{user_id}", response_model=MembershipResponse)
def set_member_role(
    assessment_id: str,
    user_id: str,
    req: SetRoleRequest,
    svc: MembershipService = Depends(get_membership_service),
    _u: str = Depends(role_guard_factory("owner")),
) -> MembershipResponse:
    return svc.set_role(assessment_id, user_id, req)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    assessment_id: str,
    user_id: str,
    svc: MembershipService = Depends(get_membership_service),
    _u: str = Depends(role_guard_factory("owner")),
) -> None:
    svc.remove_member(assessment_id, user_id)
