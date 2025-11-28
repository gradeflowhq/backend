from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, RUBRIC_YAML, SUBMISSIONS_CSV


def _rule_exact_match_q1() -> dict[str, object]:
    # Preview a single EXACT_MATCH rule targeting q1
    return {
        "type": "EXACT_MATCH",
        "question_id": "q1",
        "answer": "Alice",
        "max_points": 1.0,
    }


def test_grading_flow(api: ApiClient) -> None:
    # Setup
    created = api.create_assessment("Midterm")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    # Start grading and immediately fetch results (helper uses async run + GET)
    run = api.run_grading(created.id)

    if run.graded_submissions:
        # Get graded results
        graded = api.get_grading(created.id)
        assert len(graded.graded_submissions) >= 1

        # Export graded results (pre-adjustment)
        export = api.export_grading(created.id)
        assert export.filename.endswith(".csv")
        assert isinstance(export.data, str)

        # Adjustments: within bounds should succeed
        adjustments: list[dict[str, object]] = [
            {
                "student_id": "s2",
                "question_id": "q1",
                "adjusted_points": 1.0,
                "adjusted_feedback": "Manual override: name accepted.",
            },
            {
                "student_id": "s1",
                "question_id": "q2",
                "adjusted_points": 1.5,
                "adjusted_feedback": "Partial credit for score.",
            },
        ]
        adjusted = api.adjust_grading(created.id, adjustments=adjustments)
        assert len(adjusted.graded_submissions) >= 1

        # Verify adjusted fields present in GET
        got_after = api.get_grading(created.id)
        # Check s2 q1 adjusted to 1.0
        s2 = next(gs for gs in got_after.graded_submissions if gs.student_id == "s2")
        r_s2_q1 = next(r for r in s2.results if r.question_id == "q1")
        assert r_s2_q1.adjusted_points == 1.0
        assert r_s2_q1.adjusted_feedback == "Manual override: name accepted."

        # Check s1 q2 adjusted to 1.5
        s1 = next(gs for gs in got_after.graded_submissions if gs.student_id == "s1")
        r_s1_q2 = next(r for r in s1.results if r.question_id == "q2")
        assert r_s1_q2.adjusted_points == 1.5
        assert r_s1_q2.adjusted_feedback == "Partial credit for score."

        # Export graded results after adjustment should reflect adjusted totals
        export_after = api.export_grading(created.id)
        assert export_after.filename.endswith(".csv")
        csv_out = export_after.data
        # With the full rubric (q1, q2, q3, q4), totals after adjustment are:
        # - s1: q1=1.0 (unchanged), q2=1.5 (adjusted),
        #       q3=1.5 (A correct), q4=2.0 (1|a correct) → total 6.0
        # - s2: q1=1.0 (adjusted),  q2=2.0 (unchanged),
        #       q3=0.0 (B incorrect), q4=0.0 (2|b incorrect) → total 3.0
        assert "s1" in csv_out and "6.0" in csv_out
        assert "s2" in csv_out and "3.0" in csv_out

        # Negative test: out-of-bounds adjustment should be rejected
        bad_resp = api.try_adjust_grading(
            created.id,
            adjustments=[{"student_id": "s1", "question_id": "q2", "adjusted_points": 3.0}],
        )
        assert bad_resp.status_code == 400, bad_resp.text

        # Delete graded state
        api.delete_grading(created.id)


def test_preview_single_rule_filters_results_and_submissions(api: ApiClient) -> None:
    # Setup: assessment with question set and submissions
    created = api.create_assessment("Preview Single Rule")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    # Preview with a single rule (rubric not required when rule is provided)
    resp = api.preview_grading(
        assessment_id=created.id,
        rule=_rule_exact_match_q1(),
    )

    # We expect both s1 and s2 to be present (both answered q1), but only q1 results included
    assert len(resp.graded_submissions) >= 1
    for gs in resp.graded_submissions:
        assert all(r.question_id == "q1" for r in gs.results), "Non-target results leaked"

    # Verify pass/fail outcomes for the rule
    s1 = next(gs for gs in resp.graded_submissions if gs.student_id == "s1")
    r_s1_q1 = next(r for r in s1.results if r.question_id == "q1")
    assert r_s1_q1.passed is True

    s2 = next(gs for gs in resp.graded_submissions if gs.student_id == "s2")
    r_s2_q1 = next(r for r in s2.results if r.question_id == "q1")
    assert r_s2_q1.passed is False


def test_preview_limit_first(api: ApiClient) -> None:
    # Setup: assessment with question set, rubric (optional), submissions
    created = api.create_assessment("Preview Limit First")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    # Limit to first (by student_id sorted) => "s1"
    resp = api.preview_grading(
        assessment_id=created.id,
        limit=1,
        selection="first",
    )
    assert len(resp.graded_submissions) == 1
    assert resp.graded_submissions[0].student_id == "s1"


def test_preview_random_sampling_seed_reproducible(api: ApiClient) -> None:
    # Setup
    created = api.create_assessment("Preview Random Seed")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    # Same seed -> same sampled student
    resp1 = api.preview_grading(
        assessment_id=created.id,
        limit=1,
        selection="random",
        seed=42,
    )
    resp2 = api.preview_grading(
        assessment_id=created.id,
        limit=1,
        selection="random",
        seed=42,
    )
    assert len(resp1.graded_submissions) == 1
    assert len(resp2.graded_submissions) == 1
    assert resp1.graded_submissions[0].student_id == resp2.graded_submissions[0].student_id

    # Different seed -> different sampled student
    resp3 = api.preview_grading(
        assessment_id=created.id,
        limit=1,
        selection="random",
        seed=99,
    )
    assert len(resp3.graded_submissions) == 1
    assert resp3.graded_submissions[0].student_id != resp1.graded_submissions[0].student_id
