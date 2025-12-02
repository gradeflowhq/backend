from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session
from gradeflow_backend.dependencies.auth import get_current_user_id
from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.memberships import MembershipRepository
from gradeflow_backend.schemas.assessments import (
    AssessmentCreateRequest,
    AssessmentResponse,
    AssessmentsListResponse,
    AssessmentUpdateRequest,
)
from gradeflow_backend.services.assessments import AssessmentService

router = APIRouter(prefix="/assessments", tags=["assessments"])


def get_service(db: Session = Depends(get_session)) -> AssessmentService:
    return AssessmentService(AssessmentRepository(db), MembershipRepository(db))


@router.post("", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(
    req: AssessmentCreateRequest,
    svc: AssessmentService = Depends(get_service),
    current_user_id: str = Depends(get_current_user_id),
) -> AssessmentResponse:
    return svc.create(req, creator_user_id=current_user_id)


@router.get("", response_model=AssessmentsListResponse)
def list_assessments(
    svc: AssessmentService = Depends(get_service),
    _user: str = Depends(get_current_user_id),
) -> AssessmentsListResponse:
    items = svc.list_for_user(_user)
    return AssessmentsListResponse(items=items)


@router.get("/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(
    assessment_id: str,
    svc: AssessmentService = Depends(get_service),
    _user: str = Depends(member_guard_factory()),
) -> AssessmentResponse:
    return svc.get(assessment_id)


@router.patch("/{assessment_id}", response_model=AssessmentResponse)
def update_assessment(
    assessment_id: str,
    req: AssessmentUpdateRequest,
    svc: AssessmentService = Depends(get_service),
    _user: str = Depends(role_guard_factory("owner")),
) -> AssessmentResponse:
    return svc.update(assessment_id, req)


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(
    assessment_id: str,
    svc: AssessmentService = Depends(get_service),
    _user: str = Depends(role_guard_factory("owner")),
) -> None:
    svc.delete(assessment_id)
