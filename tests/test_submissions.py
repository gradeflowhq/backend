from __future__ import annotations

from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, SUBMISSIONS_CSV


def test_submissions_crud(api: ApiClient) -> None:
    created = api.create_assessment("Midterm")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    # Load CSV submissions
    subs = api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    assert len(subs.raw_submissions) >= 1

    # Get submissions
    got = api.get_submissions(created.id)
    assert len(got.raw_submissions) == len(subs.raw_submissions)

    # Delete submissions
    api.delete_submissions(created.id)

    # Get now returns empty list
    empty = api.get_submissions(created.id)
    assert empty.raw_submissions == []
