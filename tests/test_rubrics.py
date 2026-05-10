import yaml
from sqlalchemy.orm import Session

from gradeflow_backend.repositories.assessments import AssessmentRepository
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


def test_custom_code_rule_accepts_parameter_values_without_dtype(api: ApiClient) -> None:
    created = api.create_assessment("Custom Code Parameters")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    response = api.try_create_rule(
        created.id,
        {
            "type": "CUSTOM_CODE",
            "question_id": "q1",
            "code": "passed = answer == target\noutput = 1.0 if passed else 0.0",
            "parameters": {
                "target": {"value": "Alice"},
                "attempts": {"value": 3},
                "enabled": {"value": True},
            },
            "mode": "PASS_FAIL",
        },
    )

    assert response.status_code == 201, response.text
    parameters = response.json()["rubric"]["rules"][0]["parameters"]
    assert parameters["target"] == {"dtype": "String", "value": "Alice"}
    assert parameters["attempts"] == {"dtype": "Int", "value": 3}
    assert parameters["enabled"] == {"dtype": "Boolean", "value": True}


def test_rule_schema_lists_compatible_rules(api: ApiClient) -> None:
    created = api.create_assessment("Rule Options")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    choice_rules = api.try_list_compatible_rules(created.id, question_id="q3")
    assert choice_rules.status_code == 200, choice_rules.text
    choice_types = [rule["type"] for rule in choice_rules.json()["rules"]]
    assert "MULTIPLE_CHOICE" in choice_types
    assert "TEXT_MATCH" not in choice_types
    assert choice_rules.json()["rules"][choice_types.index("MULTIPLE_CHOICE")] == {
        "type": "MULTIPLE_CHOICE",
        "label": "Multiple Choice",
    }

    global_rules = api.try_list_compatible_rules(created.id)
    assert global_rules.status_code == 200, global_rules.text
    assert [rule["type"] for rule in global_rules.json()["rules"]] == [
        "ASSUMPTION_SET_MULTI",
        "CONDITIONAL",
        "CUSTOM_CODE_MULTI",
    ]

    slot_rules = api.try_list_compatible_rules(created.id, question_id="q4", path="rules.0")
    assert slot_rules.status_code == 200, slot_rules.text
    slot_types = [rule["type"] for rule in slot_rules.json()["rules"]]
    assert "TEXT_MATCH" in slot_types
    assert "NUMBER_EQUAL" not in slot_types


def test_rule_schema_injects_question_specific_data(api: ApiClient) -> None:
    created = api.create_assessment("Rule Schema")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    mcq = api.try_get_rule_schema(
        created.id,
        question_id="q3",
        rule_type="MULTIPLE_CHOICE",
    )
    assert mcq.status_code == 200, mcq.text
    mcq_body = mcq.json()
    answer_schema = mcq_body["schema"]["properties"]["answer"]
    assert answer_schema["items"]["enum"] == ["A", "B", "C"]
    assert mcq_body["initial_value"]["question_id"] == "q3"
    assert mcq_body["initial_value"]["type"] == "MULTIPLE_CHOICE"
    assert mcq_body["schema"]["properties"]["question_id"]["const"] == "q3"
    assert mcq_body["schema"]["properties"]["question_id"]["default"] == "q3"
    assert mcq_body["schema"]["properties"]["question_id"]["readOnly"] is True
    assert mcq_body["schema"]["properties"]["type"]["const"] == "MULTIPLE_CHOICE"
    assert mcq_body["schema"]["properties"]["type"]["default"] == "MULTIPLE_CHOICE"
    assert "ui_schema" not in mcq_body

    numeric_range = api.try_get_rule_schema(
        created.id,
        question_id="q2",
        rule_type="NUMERIC_RANGE",
    )
    assert numeric_range.status_code == 200, numeric_range.text
    numeric_body = numeric_range.json()
    min_value_schema = numeric_body["schema"]["properties"]["min_value"]
    assert "anyOf" not in min_value_schema
    assert set(min_value_schema["type"]) == {"number", "null"}

    api.set_submissions_csv(created.id, SUBMISSIONS_CSV)
    text_match = api.try_get_rule_schema(
        created.id,
        question_id="q1",
        rule_type="TEXT_MATCH",
    )
    assert text_match.status_code == 200, text_match.text
    text_body = text_match.json()
    assert text_body["schema"]["properties"]["answers"]["x-gradeflow"] == {
        "input": "string-list",
        "suggestions": ["Alice", "Bob"],
    }
    assert "examples" not in text_body["schema"]["properties"]["answers"]

    number_equal = api.try_get_rule_schema(
        created.id,
        question_id="q2",
        rule_type="NUMBER_EQUAL",
    )
    assert number_equal.status_code == 200, number_equal.text
    number_equal_body = number_equal.json()
    number_answers_schema = number_equal_body["schema"]["properties"]["answers"]
    assert number_answers_schema["items"]["type"] == "string"
    assert number_answers_schema["x-gradeflow"] == {
        "input": "string-list",
        "suggestions": ["90", "76"],
    }
    assert "examples" not in number_answers_schema

    api.set_submissions_csv(
        created.id,
        "student_id,q1,q2,q3,q4\ns1,buy house,90,A,1|a\ns2,pay,76,B,2|b\ns3,house,77,C,3|c\n",
    )
    keywords = api.try_get_rule_schema(
        created.id,
        question_id="q1",
        rule_type="KEYWORDS",
    )
    assert keywords.status_code == 200, keywords.text
    keyword_suggestions = keywords.json()["schema"]["properties"]["keywords"]["x-gradeflow"][
        "suggestions"
    ]
    assert set(keyword_suggestions) == {"buy", "pay", "house"}

    assumption_set = api.try_get_rule_schema(created.id, rule_type="ASSUMPTION_SET_MULTI")
    assert assumption_set.status_code == 200, assumption_set.text
    assumption_body = assumption_set.json()
    assert assumption_body["initial_value"]["assumptions"] == []
    assert assumption_body["schema"]["$defs"]["MultiQuestionAssumption"]["title"] == "Assumption"

    multi = api.try_get_rule_schema(
        created.id,
        question_id="q4",
        rule_type="MULTI_VALUED",
    )
    assert multi.status_code == 200, multi.text
    multi_body = multi.json()
    rules_schema = multi_body["schema"]["properties"]["rules"]
    assert multi_body["initial_value"]["rules"] == [{}, {}]
    assert rules_schema["minItems"] == 2
    assert rules_schema["maxItems"] == 2
    assert "items" in rules_schema
    assert "prefixItems" not in rules_schema
    assert rules_schema["x-gradeflow"] == {"input": "rule-list"}

    custom_code_multi = api.try_get_rule_schema(created.id, rule_type="CUSTOM_CODE_MULTI")
    assert custom_code_multi.status_code == 200, custom_code_multi.text
    custom_code_body = custom_code_multi.json()
    assert custom_code_body["schema"]["title"] == "Custom Code"
    assert custom_code_body["schema"]["properties"]["target_question_ids"]["items"]["enum"] == [
        "q1",
        "q2",
        "q3",
        "q4",
    ]
    assert "examples" not in custom_code_body["schema"]["properties"]["target_question_ids"]
    assert custom_code_body["schema"]["properties"]["target_question_ids"]["x-gradeflow"] == {
        "input": "string-list"
    }
    assert "# - q2: int | float | None" in custom_code_body["initial_value"]["code"]
    assert custom_code_body["schema"]["properties"]["code"]["x-gradeflow"] == {"input": "code"}

    code_tests = api.try_get_rule_schema(created.id, question_id="q1", rule_type="CODE_TESTS")
    assert code_tests.status_code == 200, code_tests.text
    code_test_body = code_tests.json()
    code_test_defs = code_test_body["schema"]["$defs"]
    assert code_test_defs["CodeTestCase"]["title"] == "Test Case"
    assert code_test_defs["CodeTestConfig"]["title"] == "Code Test Configuration"
    code_test_config = code_test_body["schema"]["$defs"]["CodeTestConfig"]["properties"]
    assert code_test_config["prepend_code"]["x-gradeflow"] == {"input": "code"}
    assert code_test_config["append_code"]["x-gradeflow"] == {"input": "code"}


def test_rule_schema_nested_contract(api: ApiClient) -> None:
    created = api.create_assessment("Nested Rule Schema")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    nested_question_rules = api.try_list_compatible_rules(created.id, path="then_rules.0")
    assert nested_question_rules.status_code == 200, nested_question_rules.text
    assert "TEXT_MATCH" in [rule["type"] for rule in nested_question_rules.json()["rules"]]
    assert "CONDITIONAL" not in [rule["type"] for rule in nested_question_rules.json()["rules"]]

    nested_mcq = api.try_get_rule_schema(
        created.id,
        question_id="q3",
        path="then_rules.0",
        rule_type="MULTIPLE_CHOICE",
    )
    assert nested_mcq.status_code == 200, nested_mcq.text
    nested_mcq_body = nested_mcq.json()
    nested_qid_schema = nested_mcq_body["schema"]["properties"]["question_id"]
    assert "const" not in nested_qid_schema
    assert "readOnly" not in nested_qid_schema
    assert nested_qid_schema["enum"] == ["q3"]
    assert nested_mcq_body["initial_value"]["question_id"] == "q3"
    assert nested_mcq_body["schema"]["properties"]["answer"]["items"]["enum"] == ["A", "B", "C"]

    conditional = api.try_get_rule_schema(created.id, rule_type="CONDITIONAL")
    assert conditional.status_code == 200, conditional.text
    conditional_body = conditional.json()
    assert conditional_body["schema"]["properties"]["if_rules"]["x-gradeflow"] == {
        "input": "rule-list"
    }
    assert conditional_body["schema"]["properties"]["then_rules"]["x-gradeflow"] == {
        "input": "rule-list"
    }
    assert conditional_body["schema"]["properties"]["else_rules"]["x-gradeflow"] == {
        "input": "rule-list"
    }

    nested_value_rules = api.try_list_compatible_rules(
        created.id,
        question_id="q1",
        path="rules.0",
    )
    assert nested_value_rules.status_code == 200, nested_value_rules.text
    nested_value_types = [rule["type"] for rule in nested_value_rules.json()["rules"]]
    assert "TEXT_MATCH" in nested_value_types
    assert "NUMBER_EQUAL" not in nested_value_types


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


def test_rule_request_validation_error_is_user_friendly(api: ApiClient) -> None:
    created = api.create_assessment("Friendly Rule Validation")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    created_rule = api.create_rule(
        created.id,
        {"type": "LENGTH", "question_id": "q1", "min_length": 1},
    ).rubric.rules[0]

    invalid_rule: dict[str, object] = {
        "type": "LENGTH",
        "question_id": "q1",
        "min_length": "bad",
    }

    responses = [
        api.try_create_rule(created.id, invalid_rule),
        api.try_update_rule(created.id, created_rule.id, {**invalid_rule, "id": created_rule.id}),
    ]

    for failed in responses:
        assert failed.status_code == 422, failed.text
        body = failed.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert body["message"] == "Request validation failed"
        assert body["errors"] == ["Rule > Length > min length must be a whole number."]
        assert all("Input should be" not in error for error in body["errors"])
        assert all("validation error for" not in error for error in body["errors"])


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


def test_rubric_overview_includes_stored_coverage(api: ApiClient) -> None:
    """
    Coverage using stored QuestionSet and Rubric.
    QUESTION_SET_YAML has q1 (TEXT), q2 (NUMERIC), q3 (CHOICE), q4 (MULTI_VALUED).
    RUBRIC_YAML targets q1, q2, q3, q4.
    Expect total=4, covered=4, percentage=1.0.
    """
    created = api.create_assessment("Midterm Coverage Stored")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(created.id, RUBRIC_YAML)

    cov = api.get_rubric_overview(created.id).coverage

    assert cov.total == 4
    assert cov.covered == 4
    assert cov.percentage == 1.0
    assert set(cov.question_ids) == {"q1", "q2", "q3", "q4"}
    assert set(cov.covered_question_ids) == {"q1", "q2", "q3", "q4"}
    assert set(cov.uncovered_question_ids) == set()
    assert set(cov.question_rules) == {"q1", "q2", "q3", "q4"}
    assert cov.global_rules == {}


def test_rubric_overview_coverage_includes_rule_maps(api: ApiClient) -> None:
    created = api.create_assessment("Rubric Coverage Rule Maps")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(
        created.id,
        """
rules:
  - id: direct-q1
    type: TEXT_MATCH
    question_id: q1
    answers:
      - Alice
  - id: global-q23
    type: CUSTOM_CODE_MULTI
    target_question_ids:
      - q2
      - q3
""",
    )

    overview = api.get_rubric_overview(created.id)
    coverage = overview.coverage

    assert [rule.id for rule in overview.question_rules] == ["direct-q1"]
    assert [rule.id for rule in overview.global_rules] == ["global-q23"]
    assert coverage.question_rules == {"q1": "direct-q1"}
    assert coverage.global_rules == {"q2": "global-q23", "q3": "global-q23"}
    assert coverage.questions_by_rule == {
        "direct-q1": {"q1"},
        "global-q23": {"q2", "q3"},
    }
    assert set(coverage.uncovered_question_ids) == {"q4"}


def test_rubric_overview_tolerates_invalid_stored_rule(
    api: ApiClient,
    test_session: Session,
) -> None:
    created = api.create_assessment("Rubric Overview With Broken Rule")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    AssessmentRepository(test_session).set_rubric_yaml(
        created.id,
        """
rules:
  - id: valid-q1
    type: TEXT_MATCH
    question_id: q1
    answers:
      - Alice
  - id: broken-q2
    type: LENGTH
    question_id: q2
    min_length: not-a-number
""",
    )
    test_session.commit()

    overview = api.get_rubric_overview(created.id)

    assert [rule.id for rule in overview.question_rules] == ["valid-q1"]
    assert overview.global_rules == []
    assert overview.coverage.question_rules == {"q1": "valid-q1"}
    assert overview.coverage.total == 4
    assert overview.coverage.covered == 1
    assert overview.validation_errors == ["Rule 2 > Length > min length must be a whole number."]


def test_repair_rubric_removes_invalid_stored_rules(
    api: ApiClient,
    test_session: Session,
) -> None:
    created = api.create_assessment("Repair Broken Rubric")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)

    AssessmentRepository(test_session).set_rubric_yaml(
        created.id,
        """
rules:
  - id: valid-q1
    type: TEXT_MATCH
    question_id: q1
    answers:
      - Alice
  - id: broken-q2
    type: LENGTH
    question_id: q2
    min_length: not-a-number
""",
    )
    test_session.commit()

    repaired = api.repair_rubric(created.id)

    assert [rule.id for rule in repaired.rubric.rules] == ["valid-q1"]

    stored = api.get_rubric(created.id)
    assert [rule.id for rule in stored.rubric.rules] == ["valid-q1"]

    overview = api.get_rubric_overview(created.id)
    assert [rule.id for rule in overview.question_rules] == ["valid-q1"]
    assert overview.validation_errors == []


def test_rubric_stale_rules_sync_removes_top_level_rules(api: ApiClient) -> None:
    created = api.create_assessment("Stale Rules")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(
        created.id,
        """
rules:
  - id: keep-q1
    type: TEXT_MATCH
    question_id: q1
    answers:
      - Alice
  - id: stale-qx
    type: TEXT_MATCH
    question_id: qx
    answers:
      - x
  - id: stale-global
    type: CUSTOM_CODE_MULTI
    target_question_ids:
      - q2
      - qz
""",
    )

    stale_rules = api.get_rubric_overview(created.id).stale_rules
    synced = api.sync_rubric(created.id)

    assert [(rule.rule_id, rule.qids) for rule in stale_rules] == [
        ("stale-qx", ["qx"]),
        ("stale-global", ["qz"]),
    ]
    assert [rule.id for rule in synced.rubric.rules] == ["keep-q1"]
    assert api.get_rubric_overview(created.id).stale_rules == []


def test_rubric_overview_returns_rules_coverage_stale_rules_and_status(api: ApiClient) -> None:
    created = api.create_assessment("Rubric Overview")
    api.set_question_set_yaml(created.id, QUESTION_SET_YAML)
    api.set_rubric_yaml(
        created.id,
        """
rules:
  - id: keep-q1
    type: TEXT_MATCH
    question_id: q1
    answers:
      - Alice
  - id: stale-qx
    type: TEXT_MATCH
    question_id: qx
    answers:
      - x
""",
    )

    overview = api.get_rubric_overview(created.id)

    assert [rule.id for rule in overview.question_rules] == ["keep-q1", "stale-qx"]
    assert overview.global_rules == []
    assert overview.coverage.question_rules == {"q1": "keep-q1"}
    assert overview.coverage.total == 4
    assert overview.coverage.covered == 1
    assert set(overview.coverage.uncovered_question_ids) == {"q2", "q3", "q4"}
    assert [(rule.rule_id, rule.qids) for rule in overview.stale_rules] == [
        ("stale-qx", ["qx"]),
    ]
    assert overview.status.is_stale is False


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
