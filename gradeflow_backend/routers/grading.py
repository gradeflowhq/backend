import valkey
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from gradeflow_backend.db import get_session, get_valkey
from gradeflow_backend.dependencies.memberships import member_guard_factory, role_guard_factory
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.grading_jobs import GradingJobRepository
from gradeflow_backend.schemas.grading import (
    GradeAdjustmentRequest,
    GradingDownloadRequest,
    GradingDownloadResponse,
    GradingJob,
    GradingPreviewRequest,
    GradingResponse,
    GradingRunRequest,
)
from gradeflow_backend.services.grading import GradingService
from gradeflow_backend.services.jobs import JobsService

router = APIRouter(prefix="/assessments/{assessment_id}/grading", tags=["grading"])


def get_service(
    db: Session = Depends(get_session),
    valkey_client: valkey.Valkey = Depends(get_valkey),
) -> GradingService:
    return GradingService(AssessmentRepository(db, valkey_client), GradingJobRepository(db))


def get_jobs_service(
    db: Session = Depends(get_session),
    valkey_client: valkey.Valkey = Depends(get_valkey),
) -> JobsService:
    return JobsService(db, valkey_client)


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
    return svc.get_job(assessment_id, "run", request)


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


@router.post("/download", response_model=GradingDownloadResponse, status_code=status.HTTP_200_OK)
def download_grading(
    assessment_id: str,
    req: GradingDownloadRequest,
    svc: GradingService = Depends(get_service),
    _u: str = Depends(member_guard_factory()),
) -> GradingDownloadResponse:
    return svc.download(assessment_id, req)


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
    return svc.get_job(assessment_id, "preview", request)
