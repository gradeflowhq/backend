from __future__ import annotations

from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, SUBMISSIONS_CSV


def test_question_set_crud(api: ApiClient) -> None:
    created = api.create_assessment("Midterm")

    # Set via YAML
    set_resp = api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    assert set_resp.question_set is not None

    # Get
    got = api.get_question_set(created.id)
    assert got.question_set is not None

    # Optional: parse submissions after loading sample CSV
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    parsed = api.parse_submissions(created.id)
    assert len(parsed.submissions) >= 1

    # Delete
    api.delete_question_set(created.id)

    # Getting now should 404
    resp = api.try_get_question_set(created.id)
    assert resp.status_code == 404, resp.text
