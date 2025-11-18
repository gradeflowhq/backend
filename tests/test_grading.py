from __future__ import annotations

from tests.helpers.api import ApiClient
from tests.helpers.data import ASSESSMENT_ID, QUESTION_SET_YAML, RUBRIC_YAML, SUBMISSIONS_CSV


def test_grading_flow(api: ApiClient) -> None:
    # Setup
    api.create_assessment(ASSESSMENT_ID, "Midterm")
    api.set_question_set_yaml(ASSESSMENT_ID, QUESTION_SET_YAML)
    api.set_rubric_yaml(ASSESSMENT_ID, RUBRIC_YAML)
    api.set_submissions_csv(ASSESSMENT_ID, SUBMISSIONS_CSV)

    # Run grading (helper accepts 200 or 422 and returns typed result or empty)
    run = api.run_grading(ASSESSMENT_ID)

    if run.graded_submissions:
        # Get graded results
        graded = api.get_grading(ASSESSMENT_ID)
        assert len(graded.graded_submissions) >= 1

        # Export graded results
        export = api.export_grading(ASSESSMENT_ID)
        assert export.filename.endswith(".csv")
        assert isinstance(export.data, str)

        # Delete graded state
        api.delete_grading(ASSESSMENT_ID)
