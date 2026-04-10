import pytest

from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.executors.exceptions import JobNotFoundError
from gradeflow_backend.schemas.grading import GradingJobSpec, JobStatus
from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, RUBRIC_YAML, SUBMISSIONS_CSV


class _FailingExecutor(GradingJobExecutor):
    def __init__(self, error_message: str) -> None:
        self._error_message = error_message
        self._job_id = "job-failed-run"

    def submit(self, spec: GradingJobSpec, callback_url: str) -> str:
        return self._job_id

    def get_status(self, job_id: str) -> JobStatus:
        if job_id != self._job_id:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return "failed"

    def get_error(self, job_id: str) -> str | None:
        if job_id != self._job_id:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return self._error_message

    def start(self) -> None:
        return

    def stop(self) -> None:
        return


def test_job_status_includes_failure_error(
    api: ApiClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error_message = "Engine callback failed\nTraceback (most recent call last):\n  grading.py:42"
    executor = _FailingExecutor(error_message)
    monkeypatch.setattr("gradeflow_backend.services.jobs.get_executor", lambda: executor)

    created = api.create_assessment("Failed Grading Job")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    job = api.run_grading_start(created.id)
    status = api.get_job_status(job.job_id)

    assert status.status == "failed"
    assert status.error == error_message
