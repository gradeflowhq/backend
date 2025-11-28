import yaml

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


def test_rubric_coverage_stored(api: ApiClient) -> None:
    """
    Coverage using stored QuestionSet and Rubric.
    QUESTION_SET_YAML has q1 (TEXT), q2 (NUMERIC), q3 (CHOICE), q4 (MULTI_VALUED).
    RUBRIC_YAML targets q1, q2, q3, q4.
    Expect total=4, covered=4, percentage=1.0.
    """
    created = api.create_assessment("Midterm Coverage Stored")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)

    cov = api.rubric_coverage(assessment_id=created.id).coverage

    assert cov.total == 4
    assert cov.covered == 4
    assert cov.percentage == 1.0
    assert set(cov.question_ids) == {"q1", "q2", "q3", "q4"}
    assert set(cov.covered_question_ids) == {"q1", "q2", "q3", "q4"}


def test_rubric_coverage_inline(api: ApiClient) -> None:
    """
    Coverage using inline QuestionSet and Rubric payloads (not stored).
    Provide the same YAMLs inline and expect full coverage.
    """
    created = api.create_assessment("Midterm Coverage Inline")

    qset_dict = yaml.safe_load(QUESTION_SET_YAML)
    rubric_dict = yaml.safe_load(RUBRIC_YAML)

    cov = api.rubric_coverage(
        assessment_id=created.id,
        use_stored_rubric=False,
        use_stored_question_set=False,
        rubric=rubric_dict,
        question_set=qset_dict,
    ).coverage

    assert cov.total == 4
    assert cov.covered == 4
    assert cov.percentage == 1.0
    assert set(cov.question_ids) == {"q1", "q2", "q3", "q4"}
    assert set(cov.covered_question_ids) == {"q1", "q2", "q3", "q4"}
