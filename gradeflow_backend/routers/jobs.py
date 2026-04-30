from fastapi import APIRouter, Depends, Request, status

from gradeflow_backend.dependencies.services import get_jobs_service
from gradeflow_backend.schemas.grading import GradingJobResult, JobStatusResponse
from gradeflow_backend.services.jobs import JobsService
from gradeflow_backend.utils.callback_signing import CALLBACK_SIGNATURE_HEADER

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_status(job_id: str, svc: JobsService = Depends(get_jobs_service)) -> JobStatusResponse:
    return svc.get_status(job_id)


@router.post("/callback/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def callback(
    token: str,
    request: Request,
    result: GradingJobResult,
    svc: JobsService = Depends(get_jobs_service),
) -> None:
    svc.on_callback(
        token,
        result,
        payload=await request.body(),
        signature=request.headers.get(CALLBACK_SIGNATURE_HEADER),
    )
