from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session
from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.grading import (
    GradeAdjustmentRequest,
    GradingExportRequest,
    GradingExportResponse,
    GradingJob,
    GradingPreviewRequest,
    GradingResponse,
    GradingRunRequest,
)
from gradeflow_backend.services.grading import GradingService
from gradeflow_backend.services.jobs import JobsService

router = APIRouter(prefix="/assessments/{assessment_id}/grading", tags=["grading"])


def get_service(db: Session = Depends(get_session)) -> GradingService:
    return GradingService(AssessmentRepository(db))


def get_jobs_service(db: Session = Depends(get_session)) -> JobsService:
    return JobsService(db)


@router.get("", response_model=GradingResponse)
def get_grading(
    assessment_id: str,
    svc: GradingService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> GradingResponse:
    return svc.get(assessment_id)


@router.get("/job", response_model=GradingJob, status_code=status.HTTP_200_OK)
def get_grading_job(
    assessment_id: str,
    request: Request,
    svc: GradingService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> GradingJob:
    return svc.get_job(assessment_id, request)


@router.post("", response_model=GradingJob, status_code=status.HTTP_200_OK)
def run_grading(
    assessment_id: str,
    req: GradingRunRequest,
    request: Request,
    svc: GradingService = Depends(get_service),
    jobs: JobsService = Depends(get_jobs_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> GradingJob:
    return svc.run(assessment_id, req, request, jobs)


@router.post("/adjust", response_model=GradingResponse, status_code=status.HTTP_200_OK)
def adjust_grading(
    assessment_id: str,
    req: GradeAdjustmentRequest,
    svc: GradingService = Depends(get_service),
    _u: str = Depends(role_guard_factory("editor")),
) -> GradingResponse:
    return svc.adjust(assessment_id, req)


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


@router.post("/preview", response_model=GradingJob, status_code=status.HTTP_200_OK)
def run_grading_preview(
    assessment_id: str,
    req: GradingPreviewRequest,
    request: Request,
    svc: GradingService = Depends(get_service),
    jobs: JobsService = Depends(get_jobs_service),
    _u: str = Depends(member_guard_factory()),
) -> GradingJob:
    return svc.run_preview(assessment_id, req, request, jobs)


@router.get("/preview", response_model=GradingResponse, status_code=status.HTTP_200_OK)
def get_grading_preview(
    assessment_id: str,
    svc: GradingService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> GradingResponse:
    return svc.get_preview(assessment_id)


@router.get("/preview/job", response_model=GradingJob, status_code=status.HTTP_200_OK)
def get_grading_preview_job(
    assessment_id: str,
    request: Request,
    svc: GradingService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> GradingJob:
    return svc.get_preview_job(assessment_id, request)
