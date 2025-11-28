from urllib.parse import urljoin

from fastapi import Request

from gradeflow_backend.schemas.grading import GradingJob


def build_callback_url(request: Request, token: str) -> str:
    base = str(request.base_url)
    return urljoin(base, f"jobs/callback/{token}")


def build_job_url(request: Request, job_id: str) -> str:
    base = str(request.base_url)
    return urljoin(base, f"jobs/{job_id}")


def build_grading_job(request: Request, job_id: str) -> GradingJob:
    job_url = build_job_url(request, job_id)
    return GradingJob(job_id=job_id, url=job_url)
