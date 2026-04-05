from fastapi import APIRouter, Depends, status

from gradeflow_backend.dependencies.services import get_jobs_service
from gradeflow_backend.schemas.grading import GradingJobResult, JobStatusResponse
from gradeflow_backend.services.jobs import JobsService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_status(job_id: str, svc: JobsService = Depends(get_jobs_service)) -> JobStatusResponse:
    return svc.get_status(job_id)


@router.post("/callback/{token}", status_code=status.HTTP_204_NO_CONTENT)
def callback(
    token: str, result: GradingJobResult, svc: JobsService = Depends(get_jobs_service)
) -> None:
    svc.on_callback(token, result)
