from datetime import timedelta
from posixpath import join as urljoin
from uuid import uuid4

from fastapi import Request

from gradeflow_backend.config import get_settings
from gradeflow_backend.models.grading_job import GradingJobRecord
from gradeflow_backend.schemas.grading import (
    GradingJob,
    JobStatus,
    JobStatusResponse,
    JobTiming,
    JobType,
)
from gradeflow_backend.utils.datetime import ensure_utc


def make_grading_job_id(job_type: JobType) -> str:
    return f"job-{uuid4().hex}-{job_type}"


def build_callback_url(request: Request, token: str) -> str:
    base = (get_settings().executor.callback_base_url or str(request.base_url)).strip()
    return urljoin(base, f"jobs/callback/{token}")


def build_job_url(request: Request, job_id: str) -> str:
    base = str(request.base_url)
    return urljoin(base, f"jobs/{job_id}")


def build_grading_job(
    request: Request,
    record: GradingJobRecord,
    *,
    estimated_duration_seconds: float | None = None,
) -> GradingJob:
    job_url = build_job_url(request, record.job_id)
    return GradingJob(
        job_id=record.job_id,
        url=job_url,
        created_at=ensure_utc(record.created_at),
        **build_job_timing(
            record,
            estimated_duration_seconds=estimated_duration_seconds,
        ).model_dump(),
    )


def build_job_status_response(
    *,
    record: GradingJobRecord,
    status: JobStatus,
    error: str | None = None,
    estimated_duration_seconds: float | None = None,
) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=record.job_id,
        status=status,
        error=error,
        created_at=ensure_utc(record.created_at),
        **build_job_timing(
            record,
            estimated_duration_seconds=estimated_duration_seconds,
        ).model_dump(),
    )


def build_job_timing(
    record: GradingJobRecord,
    *,
    estimated_duration_seconds: float | None = None,
) -> JobTiming:
    estimated_completion_at = None
    if not record.is_completed and estimated_duration_seconds is not None:
        estimated_completion_at = ensure_utc(record.created_at) + timedelta(
            seconds=estimated_duration_seconds
        )
    return JobTiming(
        is_completed=record.is_completed,
        completed_at=ensure_utc(record.completed_at) if record.completed_at else None,
        duration_seconds=record.duration_seconds,
        estimated_duration_seconds=estimated_duration_seconds if not record.is_completed else None,
        estimated_completion_at=estimated_completion_at,
    )
