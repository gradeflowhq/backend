from typing import Any, cast

import pytest

from gradeflow_backend.config import get_settings
from gradeflow_backend.dependencies.executor import get_executor
from gradeflow_backend.executors.base import GradingJobExecutor
from gradeflow_backend.executors.exceptions import JobNotFoundError
from gradeflow_backend.main import app
from gradeflow_backend.schemas.grading import GradingJobSpec, JobStatus
from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, RUBRIC_YAML, SUBMISSIONS_CSV


class _FailingExecutor(GradingJobExecutor):
    def __init__(self, error_message: str) -> None:
        self._error_message = error_message
        self._job_id = ""

    def submit(
        self,
        job_id: str,
        spec: GradingJobSpec,
        callback_url: str,
        callback_secret: str,
    ) -> None:
        self._job_id = job_id

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


class _CapturingExecutor(GradingJobExecutor):
    def __init__(self) -> None:
        self.spec: GradingJobSpec | None = None
        self._job_id = ""

    def submit(
        self,
        job_id: str,
        spec: GradingJobSpec,
        callback_url: str,
        callback_secret: str,
    ) -> None:
        self._job_id = job_id
        self.spec = spec

    def get_status(self, job_id: str) -> JobStatus:
        if job_id != self._job_id:
            raise JobNotFoundError(f"Job not found: {job_id}")
        return "queued"

    def start(self) -> None:
        return

    def stop(self) -> None:
        return


class _SubmitFailingExecutor(GradingJobExecutor):
    def submit(
        self,
        job_id: str,
        spec: GradingJobSpec,
        callback_url: str,
        callback_secret: str,
    ) -> None:
        raise ConnectionError("Nomad is unavailable")

    def get_status(self, job_id: str) -> JobStatus:
        raise JobNotFoundError(f"Job not found: {job_id}")

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
    monkeypatch.setitem(
        cast(dict[Any, Any], app.dependency_overrides), get_executor, lambda: executor
    )

    created = api.create_assessment("Failed Grading Job")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    job = api.run_grading_start(created.id)
    status = api.get_job_status(job.job_id)

    assert status.status == "failed"
    assert status.error == error_message


def test_job_submission_executor_failure_returns_structured_503(
    api: ApiClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _SubmitFailingExecutor()
    monkeypatch.setitem(
        cast(dict[Any, Any], app.dependency_overrides), get_executor, lambda: executor
    )

    created = api.create_assessment("Executor Unavailable")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    response = api.try_run_grading(created.id)

    assert response.status_code == 503, response.text
    body = response.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert body["message"] == (
        "Unable to start grading job. The grading executor is unavailable "
        "or failed to accept the job."
    )
    assert body["errors"] == [body["message"]]


def test_grading_job_spec_uses_parallel_grading_settings(
    api: ApiClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings.grading, "rubric_grading_parallel_jobs", 3)
    monkeypatch.setattr(settings.grading, "rubric_grading_parallel_mode", "threads")
    executor = _CapturingExecutor()
    monkeypatch.setitem(
        cast(dict[Any, Any], app.dependency_overrides), get_executor, lambda: executor
    )

    created = api.create_assessment("Parallel Grading Settings")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    api.run_grading_start(created.id)

    assert executor.spec is not None
    assert executor.spec.rubric_grading_parallel_jobs == 3
    assert executor.spec.rubric_grading_parallel_mode == "threads"
