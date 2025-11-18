from __future__ import annotations

from tests.helpers.api import ApiClient
from tests.helpers.data import ASSESSMENT_ID, QUESTION_SET_YAML, SUBMISSIONS_CSV


def test_question_set_crud(api: ApiClient) -> None:
    api.create_assessment(ASSESSMENT_ID, "Midterm")

    # Set via YAML
    set_resp = api.set_question_set_yaml(ASSESSMENT_ID, QUESTION_SET_YAML)
    assert set_resp.question_set is not None

    # Get
    got = api.get_question_set(ASSESSMENT_ID)
    assert got.question_set is not None

    # Optional: parse submissions after loading sample CSV
    api.set_submissions_csv(ASSESSMENT_ID, SUBMISSIONS_CSV)
    parsed = api.parse_submissions(ASSESSMENT_ID)
    assert len(parsed.submissions) >= 1

    # Delete
    api.delete_question_set(ASSESSMENT_ID)

    # Getting now should 404
    resp = api.try_get_question_set(ASSESSMENT_ID)
    assert resp.status_code == 404, resp.text
