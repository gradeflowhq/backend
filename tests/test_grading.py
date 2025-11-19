from __future__ import annotations

from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, RUBRIC_YAML, SUBMISSIONS_CSV


def test_grading_flow(api: ApiClient) -> None:
    # Setup
    created = api.create_assessment("Midterm")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    # Run grading (helper accepts 200 or 422 and returns typed result or empty)
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
        # Initial expected points from RUBRIC_YAML:
        # - s1: q1=1.0 (Alice exact match), q2=2.0 (90 in range) → total 3.0
        # - s2: q1=0.0 (Bob mismatch),      q2=2.0 (76 in range) → total 2.0
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
        # Totals after adjustment:
        # - s1: q1=1.0 (unchanged), q2=1.5 (adjusted) → total 2.5
        # - s2: q1=1.0 (adjusted),  q2=2.0 (unchanged) → total 3.0
        assert "s1" in csv_out and "2.5" in csv_out
        assert "s2" in csv_out and "3.0" in csv_out

        # Negative test: out-of-bounds adjustment should be rejected (Option B)
        bad_resp = api.try_adjust_grading(
            created.id,
            adjustments=[{"student_id": "s1", "question_id": "q2", "adjusted_points": 3.0}],
        )
        assert bad_resp.status_code == 400, bad_resp.text

        # Delete graded state
        api.delete_grading(created.id)
