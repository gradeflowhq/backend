from __future__ import annotations

from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, RUBRIC_YAML


def test_rubric_set_get_validate_delete(api: ApiClient) -> None:
    created = api.create_assessment("Midterm")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    # Set rubric
    rub = api.set_rubric_yaml(created.id, RUBRIC_YAML)
    assert rub.rubric is not None

    # Get rubric
    got = api.get_rubric(created.id)
    assert got.rubric is not None

    # Validate rubric (200 if valid, 422 if invalid; helper normalizes to a typed response)
    val = api.validate_rubric(created.id)
    assert isinstance(val.errors, list)

    # Delete rubric
    api.delete_rubric(created.id)

    # Getting now should 404
    resp = api.try_get_rubric(created.id)
    assert resp.status_code == 404, resp.text
