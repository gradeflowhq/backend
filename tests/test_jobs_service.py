from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, RUBRIC_YAML, SUBMISSIONS_CSV


def test_callback_with_invalid_token_rejected(api: ApiClient) -> None:
    r = api.try_callback(
        "totally-invalid-token",
        assessment_id="fake",
        type="run",
        submissions=[],
        remove_adjustments=False,
    )
    assert r.status_code == 404, r.text


def test_get_job_status_unknown_job(api: ApiClient) -> None:
    r = api.try_get_job_status("unknown-job-id-xyz")
    assert r.status_code == 404, r.text


def test_cancel_grading_job_not_found(api: ApiClient) -> None:
    created = api.create_assessment("Cancel No Job")
    r = api.try_cancel_grading_job(created.id)
    assert r.status_code == 404, r.text


def test_cancel_preview_job_not_found(api: ApiClient) -> None:
    created = api.create_assessment("Cancel No Preview Job")
    r = api.try_cancel_preview_job(created.id)
    # member_guard_factory() — viewer is fine; no job → 404
    assert r.status_code == 404, r.text


def test_get_preview_job_not_found(api: ApiClient) -> None:
    created = api.create_assessment("Preview Job Not Found")
    r = api.try_get_preview_job(created.id)
    assert r.status_code == 404, r.text


def test_full_grading_job_status_lifecycle(api: ApiClient) -> None:
    """After a synchronous run the job status should be 'completed'."""
    created = api.create_assessment("Job Lifecycle")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    job = api.run_grading_start(created.id)
    status = api.get_job_status(job.job_id)
    # Synchronous executor completes inline
    assert status.status == "completed"
    assert status.error is None
