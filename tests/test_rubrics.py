import yaml

from tests.helpers.api import ApiClient
from tests.helpers.data import QUESTION_SET_YAML, RUBRIC_YAML, SUBMISSIONS_CSV


def test_rubric_set_get_validate_delete(api: ApiClient) -> None:
    created = api.create_assessment("Midterm")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    # Set rubric (serializer-based upload)
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


def test_rubric_import_examplify_adapter_and_validate(api: ApiClient) -> None:
    created = api.create_assessment("Rubric Import via Adapter")

    # Import a matching QuestionSet via adapter (Choice Q1 with A,B)
    examplify_qset_csv = (
        "Seq,Type,Item Text,Original Answer,Adjusted Answer,ThrowOut\n"
        "1,Choice,Pick letters,A,B,FALSE\n"
    )
    _ = api.import_question_set(
        created.id,
        data=examplify_qset_csv,
        adapter={"name": "examplify"},
    )

    # Minimal Examplify-like rubric CSV for the same Q1: correct answer A, 1.5 points
    examplify_rubric_csv = (
        "Seq,Type,Original Answer,Adjusted Answer,Adjusted Points,GiveFullCreditToAllETs,ThrowOut\n"
        "1,Choice,A,,1.5,FALSE,FALSE\n"
    )

    _ = api.import_rubric(
        created.id,
        data=examplify_rubric_csv,
        adapter={"name": "examplify"},
    )

    # Validate rubric against stored question set
    val = api.validate_rubric(created.id)
    assert isinstance(val.errors, list)
    assert len(val.errors) == 0, f"Unexpected validation errors: {val.errors}"


def test_rubric_status_inherit_submission_staleness(api: ApiClient) -> None:
    created = api.create_assessment("Rubric Status")

    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)

    question_set = api.get_question_set(created.id)
    rubric = api.get_rubric(created.id)

    assert question_set.status.is_stale is True
    assert rubric.status.is_stale is True


def test_rubric_status_clears_after_question_set_change_is_acknowledged(api: ApiClient) -> None:
    created = api.create_assessment("Rubric Status Refresh")

    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    stale = api.get_rubric(created.id)
    assert stale.status.is_stale is True

    refreshed = api.set_rubric_yaml(created.id, RUBRIC_YAML)
    assert refreshed.status.is_stale is False


def test_rubric_export(api: ApiClient) -> None:
    created = api.create_assessment("Rubric Export")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)

    exported = api.export_rubric(created.id)

    assert exported.extension == "yaml"
    assert exported.media_type
    assert exported.filename == "rubric-export-rules.yaml"
    assert b"rules:" in exported.data
