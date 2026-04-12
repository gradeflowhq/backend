from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, RUBRIC_YAML, SUBMISSIONS_CSV


def _rule_exact_match_q1() -> dict[str, object]:
    return {
        "type": "TEXT_MATCH",
        "question_id": "q1",
        "answers": ["Alice"],
        "max_points": 1.0,
    }


def test_grading_flow(api: ApiClient) -> None:
    created = api.create_assessment("Midterm")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    run = api.run_grading(created.id)

    if run.submissions:
        graded = api.get_grading(created.id)
        assert len(graded.submissions) >= 1

        dl = api.download_grading(created.id)
        assert dl.filename.endswith(".csv")
        assert isinstance(dl.data, (bytes, bytearray))

        api.adjust_grading(
            created.id,
            adjustment={
                "student_id": "s2",
                "question_id": "q1",
                "adjusted_points": 1.0,
                "adjusted_feedback": "Manual override: name accepted.",
            },
        )
        adjusted = api.adjust_grading(
            created.id,
            adjustment={
                "student_id": "s1",
                "question_id": "q2",
                "adjusted_points": 1.5,
                "adjusted_feedback": "Partial credit for score.",
            },
        )
        assert len(adjusted.submissions) >= 1

        got_after = api.get_grading(created.id)
        s2 = next(gs for gs in got_after.submissions if gs.student_id == "s2")
        r_s2_q1 = s2.result_map["q1"]
        assert r_s2_q1.adjusted_points == 1.0
        assert r_s2_q1.adjusted_feedback == "Manual override: name accepted."

        s1 = next(gs for gs in got_after.submissions if gs.student_id == "s1")
        r_s1_q2 = s1.result_map["q2"]
        assert r_s1_q2.adjusted_points == 1.5
        assert r_s1_q2.adjusted_feedback == "Partial credit for score."

        dl_after = api.download_grading(created.id)
        assert dl_after.filename.endswith(".csv")
        csv_out = dl_after.data.decode("utf-8", errors="replace")
        assert "s1" in csv_out and "6.0" in csv_out
        assert "s2" in csv_out and "3.0" in csv_out

        bad_resp = api.try_adjust_grading(
            created.id,
            adjustment={"student_id": "s1", "question_id": "q2", "adjusted_points": 3.0},
        )
        assert bad_resp.status_code == 400, bad_resp.text

        api.delete_grading(created.id)


def test_download_grading_no_results(api: ApiClient) -> None:
    """Downloading before any grading run must return 400."""
    created = api.create_assessment("No Results Download")
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)

    r = api.try_download_grading(created.id)
    assert r.status_code == 400, r.text


def test_bulk_adjust_all_valid(api: ApiClient) -> None:
    created = api.create_assessment("Bulk Adjust All Valid")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    api.run_grading(created.id)

    r = api.try_bulk_adjust(
        created.id,
        adjustments=[
            {"student_id": "s1", "question_id": "q1", "adjusted_points": 0.5},
            {"student_id": "s2", "question_id": "q2", "adjusted_points": 1.0},
        ],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] == 2
    assert body["errors"] == []

    # Verify adjustments persisted
    subs = {gs["student_id"]: gs for gs in body["result"]["submissions"]}
    assert subs["s1"]["result_map"]["q1"]["adjusted_points"] == 0.5
    assert subs["s2"]["result_map"]["q2"]["adjusted_points"] == 1.0


def test_bulk_adjust_partial_errors(api: ApiClient) -> None:
    """Bulk adjust where some entries are invalid (bad student/question) and some are valid."""
    created = api.create_assessment("Bulk Adjust Partial")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    api.run_grading(created.id)

    r = api.try_bulk_adjust(
        created.id,
        adjustments=[
            # Valid
            {"student_id": "s1", "question_id": "q1", "adjusted_points": 0.5},
            # Invalid: student does not exist
            {"student_id": "s_ghost", "question_id": "q1", "adjusted_points": 1.0},
            # Invalid: points exceed max
            {"student_id": "s2", "question_id": "q2", "adjusted_points": 999.0},
        ],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["applied"] == 1
    assert len(body["errors"]) == 2


def test_bulk_adjust_empty_list_rejected(api: ApiClient) -> None:
    created = api.create_assessment("Bulk Empty")
    r = api.try_bulk_adjust(created.id, adjustments=[])
    # Pydantic min_length=1 on adjustments list → 422
    assert r.status_code == 422, r.text


def test_get_grading_job_not_found(api: ApiClient) -> None:
    created = api.create_assessment("No Job")
    r = api.try_get_grading_job(created.id)
    assert r.status_code == 404, r.text


def test_get_grading_job_found(api: ApiClient) -> None:
    created = api.create_assessment("With Job")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    api.run_grading_start(created.id)

    r = api.try_get_grading_job(created.id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "job_id" in body
    assert "url" in body


def test_grading_run_removes_adjustments_flag(api: ApiClient) -> None:
    """Re-running with remove_adjustments=True must clear prior manual adjustments."""
    created = api.create_assessment("Remove Adjustments")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    api.run_grading(created.id)

    # Apply an adjustment
    api.adjust_grading(
        created.id,
        adjustment={"student_id": "s1", "question_id": "q1", "adjusted_points": 0.0},
    )

    # Re-run with remove_adjustments=True
    r = api.try_run_grading(created.id, remove_adjustments=True)
    assert r.status_code == 200, r.text

    graded = api.get_grading(created.id)
    s1 = next(gs for gs in graded.submissions if gs.student_id == "s1")
    assert s1.result_map["q1"].adjusted_points is None


def test_preview_single_rule_filters_results_and_submissions(api: ApiClient) -> None:
    created = api.create_assessment("Preview Single Rule")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    resp = api.preview_grading(
        assessment_id=created.id,
        rule=_rule_exact_match_q1(),
    )

    assert len(resp.submissions) >= 1
    for gs in resp.submissions:
        assert all(qid == "q1" for qid in gs.result_map), "Non-target results leaked"

    s1 = next(gs for gs in resp.submissions if gs.student_id == "s1")
    assert s1.result_map["q1"].passed is True

    s2 = next(gs for gs in resp.submissions if gs.student_id == "s2")
    assert s2.result_map["q1"].passed is False


def test_preview_clears_existing_results(api: ApiClient) -> None:
    created = api.create_assessment("Preview Clears Existing Results")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    full = api.run_grading(created.id)
    assert full.submissions, "Expected graded submissions before preview"
    s1_full = next(gs for gs in full.submissions if gs.student_id == "s1")
    assert len(s1_full.result_map) > 1

    preview = api.preview_grading(
        assessment_id=created.id,
        rule=_rule_exact_match_q1(),
    )

    assert preview.submissions, "Expected preview submissions"
    for gs in preview.submissions:
        assert set(gs.result_map.keys()) == {"q1"}, (
            f"Preview for {gs.student_id} leaked non-target results: {set(gs.result_map.keys())}"
        )


def test_preview_limit_first(api: ApiClient) -> None:
    created = api.create_assessment("Preview Limit First")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    resp = api.preview_grading(
        assessment_id=created.id,
        limit=1,
        selection="first",
    )
    assert len(resp.submissions) == 1
    assert resp.submissions[0].student_id == "s1"


def test_preview_random_sampling_seed_reproducible(api: ApiClient) -> None:
    created = api.create_assessment("Preview Random Seed")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    resp1 = api.preview_grading(assessment_id=created.id, limit=1, selection="random", seed=42)
    resp2 = api.preview_grading(assessment_id=created.id, limit=1, selection="random", seed=42)
    assert resp1.submissions[0].student_id == resp2.submissions[0].student_id

    resp3 = api.preview_grading(assessment_id=created.id, limit=1, selection="random", seed=99)
    assert resp3.submissions[0].student_id != resp1.submissions[0].student_id


def test_adjust_nonexistent_student_rejected(api: ApiClient) -> None:
    created = api.create_assessment("Adjust Ghost Student")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    api.run_grading(created.id)

    r = api.try_adjust_grading(
        created.id,
        adjustment={"student_id": "ghost", "question_id": "q1", "adjusted_points": 1.0},
    )
    assert r.status_code == 400, r.text


def test_grading_requires_editor_role(api: ApiClient) -> None:
    from gradeflow_backend.schemas.auth import TokenPairResponse

    other = ApiClient(api.client)
    tokens: TokenPairResponse = other.signup("viewer_grade@example.com", "Strong-Pass-12345!")
    other.set_access_token(tokens.access_token)

    created = api.create_assessment("Editor Guard Grading")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    api.add_member(created.id, user_email="viewer_grade@example.com", role="viewer")

    r = other.try_run_grading(created.id)
    assert r.status_code == 403, r.text
