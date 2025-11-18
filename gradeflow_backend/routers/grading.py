from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session
from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.grading import (
    GradingExportRequest,
    GradingExportResponse,
    GradingResponse,
    GradingRunRequest,
)
from gradeflow_backend.services.grading import GradingService

router = APIRouter(prefix="/assessments/{assessment_id}/grading", tags=["grading"])


def get_service(db: Session = Depends(get_session)) -> GradingService:
    return GradingService(AssessmentRepository(db))


@router.get("", response_model=GradingResponse)
def get_grading(
    assessment_id: str,
    svc: GradingService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> GradingResponse:
    return svc.get(assessment_id)


@router.post("/run", response_model=GradingResponse, status_code=status.HTTP_200_OK)
def run_grading(
    assessment_id: str,
    req: GradingRunRequest,
    svc: GradingService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> GradingResponse:
    return svc.run(assessment_id, req)


@router.post("/export", response_model=GradingExportResponse, status_code=status.HTTP_200_OK)
def export_grading(
    assessment_id: str,
    req: GradingExportRequest,
    svc: GradingService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> GradingExportResponse:
    return svc.export(assessment_id, req)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_grading(
    assessment_id: str,
    svc: GradingService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> None:
    svc.delete(assessment_id)
