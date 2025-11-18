from __future__ import annotations

from tests.helpers.api import ApiClient
from tests.helpers.data import ASSESSMENT_ID, QUESTION_SET_YAML, SUBMISSIONS_CSV


def test_submissions_crud(api: ApiClient) -> None:
    api.create_assessment(ASSESSMENT_ID, "Midterm")
    api.set_question_set_yaml(ASSESSMENT_ID, QUESTION_SET_YAML)

    # Load CSV submissions
    subs = api.set_submissions_csv(ASSESSMENT_ID, SUBMISSIONS_CSV)
    assert len(subs.raw_submissions) >= 1

    # Get submissions
    got = api.get_submissions(ASSESSMENT_ID)
    assert len(got.raw_submissions) == len(subs.raw_submissions)

    # Delete submissions
    api.delete_submissions(ASSESSMENT_ID)

    # Get now returns empty list
    empty = api.get_submissions(ASSESSMENT_ID)
    assert empty.raw_submissions == []
