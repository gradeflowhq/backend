from __future__ import annotations

from tests.helpers.api import ApiClient
from tests.helpers.data import ASSESSMENT_ID, QUESTION_SET_YAML, RUBRIC_YAML


def test_rubric_set_get_validate_delete(api: ApiClient) -> None:
    api.create_assessment(ASSESSMENT_ID, "Midterm")
    api.set_question_set_yaml(ASSESSMENT_ID, QUESTION_SET_YAML)

    # Set rubric
    rub = api.set_rubric_yaml(ASSESSMENT_ID, RUBRIC_YAML)
    assert rub.rubric is not None

    # Get rubric
    got = api.get_rubric(ASSESSMENT_ID)
    assert got.rubric is not None

    # Validate rubric (200 if valid, 422 if invalid; helper normalizes to a typed response)
    val = api.validate_rubric(ASSESSMENT_ID)
    assert isinstance(val.errors, list)

    # Delete rubric
    api.delete_rubric(ASSESSMENT_ID)

    # Getting now should 404
    resp = api.try_get_rubric(ASSESSMENT_ID)
    assert resp.status_code == 404, resp.text
