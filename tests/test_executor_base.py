from gradeflow_backend.executors.base import format_job_error


def test_none_returns_default() -> None:
    assert format_job_error(None) == "Job failed unexpectedly."


def test_empty_string_returns_default() -> None:
    assert format_job_error("") == "Job failed unexpectedly."


def test_whitespace_only_returns_default() -> None:
    assert format_job_error("   ") == "Job failed unexpectedly."


def test_exception_returns_message() -> None:
    assert format_job_error(Exception("boom")) == "boom"


def test_string_returns_as_is() -> None:
    assert format_job_error("custom error") == "custom error"
