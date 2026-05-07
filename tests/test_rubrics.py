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


def test_rule_crud(api: ApiClient) -> None:
    created = api.create_assessment("Rule CRUD")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    rubric_dict = yaml.safe_load(RUBRIC_YAML)
    text_rule = rubric_dict["rules"][0]
    numeric_rule = rubric_dict["rules"][1]

    created_rubric = api.create_rule(created.id, text_rule)
    assert len(created_rubric.rubric.rules) == 1
    assert created_rubric.rubric.rules[0].type == "TEXT_MATCH"
    rule_id = created_rubric.rubric.rules[0].id
    assert len(rule_id) == 32

    listed = api.try_list_rules(created.id)
    assert listed.status_code == 200, listed.text
    listed_body = listed.json()
    assert "rule_id" not in listed_body["rules"][0]
    assert [rule["id"] for rule in listed_body["rules"]] == [rule_id]
    assert listed_body["rules"][0]["type"] == "TEXT_MATCH"

    got = api.try_get_rule(created.id, rule_id)
    assert got.status_code == 200, got.text
    assert got.json()["question_id"] == "q1"

    updated_rubric = api.update_rule(created.id, rule_id, {**numeric_rule, "id": rule_id})
    assert len(updated_rubric.rubric.rules) == 1
    assert updated_rubric.rubric.rules[0].type == "NUMERIC_RANGE"
    assert updated_rubric.rubric.rules[0].id == rule_id

    api.create_rule(created.id, text_rule)
    api.delete_rule(created.id, rule_id)

    remaining = api.get_rubric(created.id).rubric.rules
    assert len(remaining) == 1
    assert remaining[0].type == "TEXT_MATCH"


def test_rule_create_ignores_client_supplied_id(api: ApiClient) -> None:
    created = api.create_assessment("Rule ID Authority")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    rubric_dict = yaml.safe_load(RUBRIC_YAML)
    requested_rule = {**rubric_dict["rules"][0], "id": "client-id"}

    created_rubric = api.create_rule(created.id, requested_rule)

    assert created_rubric.rubric.rules[0].id != "client-id"
    assert len(created_rubric.rubric.rules[0].id) == 32


def test_rule_update_requires_matching_body_id(api: ApiClient) -> None:
    created = api.create_assessment("Rule ID Match")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    rubric_dict = yaml.safe_load(RUBRIC_YAML)
    text_rule = rubric_dict["rules"][0]
    numeric_rule = rubric_dict["rules"][1]

    created_rubric = api.create_rule(created.id, text_rule)
    rule_id = created_rubric.rubric.rules[0].id

    failed = api.try_update_rule(created.id, rule_id, {**numeric_rule, "id": "different"})

    assert failed.status_code == 400, failed.text
    assert failed.json()["code"] == "BAD_REQUEST"

    unchanged = api.get_rubric(created.id).rubric.rules
    assert len(unchanged) == 1
    assert unchanged[0].id == rule_id
    assert unchanged[0].type == "TEXT_MATCH"


def test_rule_update_validates_prospective_rubric(api: ApiClient) -> None:
    created = api.create_assessment("Rule Validation")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    rubric_dict = yaml.safe_load(RUBRIC_YAML)
    text_rule = rubric_dict["rules"][0]
    created_rubric = api.create_rule(created.id, text_rule)
    assert getattr(created_rubric.rubric.rules[0], "question_id", None) == "q1"
    rule_id = created_rubric.rubric.rules[0].id
    invalid_rule = {**text_rule, "id": rule_id, "question_id": "missing"}

    failed = api.try_update_rule(created.id, rule_id, invalid_rule)
    assert failed.status_code == 422, failed.text
    assert failed.json()["code"] == "RUBRIC_VALIDATION_ERROR"

    unchanged = api.get_rubric(created.id).rubric.rules
    assert len(unchanged) == 1
    assert getattr(unchanged[0], "question_id", None) == "q1"


def test_create_empty_rubric_creates_empty_rubric(api: ApiClient) -> None:
    created = api.create_assessment("Empty Rules")

    before = api.try_get_rubric(created.id)
    assert before.status_code == 404, before.text

    created_empty = api.create_empty_rubric(created.id)

    assert created_empty.rubric.rules == []
    assert api.get_rubric(created.id).rubric.rules == []


def test_create_empty_rubric_rejects_existing_rubric(api: ApiClient) -> None:
    created = api.create_assessment("Existing Rules")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)

    failed = api.try_create_empty_rubric(created.id)

    assert failed.status_code == 400, failed.text
    assert failed.json()["code"] == "BAD_REQUEST"


def test_acknowledge_rubric_staleness_requires_existing_rubric(api: ApiClient) -> None:
    created = api.create_assessment("No Rules")

    failed = api.try_acknowledge_rubric_staleness(created.id)

    assert failed.status_code == 404, failed.text
    assert failed.json()["code"] == "NOT_FOUND"


def test_acknowledge_rubric_staleness_clears_stale_status(api: ApiClient) -> None:
    created = api.create_assessment("Rubric Status Acknowledge")

    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    stale = api.get_rubric(created.id)
    assert stale.status.is_stale is True

    refreshed = api.acknowledge_rubric_staleness(created.id)

    assert refreshed.status.is_stale is False


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
