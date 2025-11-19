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

        # Export graded results
        export = api.export_grading(created.id)
        assert export.filename.endswith(".csv")
        assert isinstance(export.data, str)

        # Delete graded state
        api.delete_grading(created.id)
