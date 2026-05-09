import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import yaml

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "migrations"
    / "versions"
    / "2d8f9c1a7b3e_assign_missing_rule_ids.py"
)


def _normalize_rubric_yaml(rubric_yaml: str) -> str | None:
    namespace = runpy.run_path(str(MIGRATION_PATH))
    normalize = cast(Callable[[str], str | None], namespace["_normalize_rubric_yaml"])
    return normalize(rubric_yaml)


def _load_yaml(data: str) -> dict[str, Any]:
    loaded = yaml.safe_load(data)
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def _as_dict(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _as_list(value: object) -> list[Any]:
    assert isinstance(value, list)
    return value


def _assert_rule_has_id(rule: object) -> dict[str, Any]:
    rule_data = _as_dict(rule)
    assert isinstance(rule_data.get("id"), str)
    assert rule_data["id"]
    return rule_data


def test_normalize_rubric_yaml_assigns_ids_to_rules_only() -> None:
    normalized = _normalize_rubric_yaml(
        """
rules:
  - type: COMPOSITE
    question_id: q1
    constraints:
      - type: CHOICE
        source: options
        target: answer
    rules:
      - type: TEXT_MATCH
        answers: [yes]
      - type: LENGTH
        id: existing-child
        min_length: 3
  - type: CONDITIONAL
    if_rules:
      - type: KEYWORDS
        question_id: q2
        keywords: [ready]
    then_rules:
      - type: TEXT_MATCH
        question_id: q3
        answers: [done]
    else_rules: []
  - type: ASSUMPTION_SET
    question_id: q4
    assumptions:
      - name: interpretation
        rule:
          type: NUMBER_EQUAL
          answers: [1]
  - type: ASSUMPTION_SET_MULTI
    assumptions:
      - rules:
          - type: NUMERIC_RANGE
            question_id: q5
            min_value: 0
            max_value: 10
"""
    )

    assert normalized is not None
    data = _load_yaml(normalized)
    rules = cast(list[dict[str, Any]], data["rules"])

    assert all(isinstance(rule.get("id"), str) for rule in rules)
    assert "id" not in cast(list[dict[str, Any]], rules[0]["constraints"])[0]
    assert cast(list[dict[str, Any]], rules[0]["rules"])[0]["id"]
    assert cast(list[dict[str, Any]], rules[0]["rules"])[1]["id"] == "existing-child"
    assert cast(list[dict[str, Any]], rules[1]["if_rules"])[0]["id"]
    assert cast(list[dict[str, Any]], rules[1]["then_rules"])[0]["id"]

    assumption = cast(list[dict[str, Any]], rules[2]["assumptions"])[0]
    assert "id" not in assumption
    assert cast(dict[str, Any], assumption["rule"])["id"]

    multi_assumption = cast(list[dict[str, Any]], rules[3]["assumptions"])[0]
    assert cast(list[dict[str, Any]], multi_assumption["rules"])[0]["id"]


def test_normalize_rubric_yaml_returns_none_when_all_rule_ids_exist() -> None:
    normalized = _normalize_rubric_yaml(
        """
rules:
  - type: COMPOSITE
    id: root
    question_id: q1
    rules:
      - type: TEXT_MATCH
        id: child
        answers: [yes]
"""
    )

    assert normalized is None


def test_normalize_rubric_yaml_assigns_ids_to_all_rule_container_shapes() -> None:
    normalized = _normalize_rubric_yaml(
        """
rules:
  - type: COMPOSITE
    question_id: q1
    rules:
      - type: MULTI_VALUED
        rules:
          - type: TEXT_MATCH
            answers: [alpha]
          - type: COMPOSITE
            rules:
              - type: REGEX
                pattern: beta
      - type: ASSUMPTION_SET
        question_id: q2
        assumptions:
          - rule:
              type: LENGTH
              min_length: 3
  - type: CONDITIONAL
    if_rules:
      - type: COMPOSITE
        question_id: q3
        rules:
          - type: KEYWORDS
            keywords: [ready]
    then_rules:
      - type: MULTI_VALUED
        question_id: q4
        rules:
          - type: NUMBER_EQUAL
            answers: [1]
    else_rules:
      - type: ASSUMPTION_SET
        question_id: q5
        assumptions:
          - rule:
              type: NUMERIC_RANGE
              min_value: 0
              max_value: 10
  - type: ASSUMPTION_SET_MULTI
    assumptions:
      - rules:
          - type: CONDITIONAL
            if_rules:
              - type: TEXT_MATCH
                question_id: q6
                answers: [yes]
            then_rules:
              - type: BONUS
                question_id: q7
            else_rules: []
"""
    )

    assert normalized is not None
    data = _load_yaml(normalized)
    rules = _as_list(data["rules"])

    composite = _assert_rule_has_id(rules[0])
    composite_children = _as_list(composite["rules"])
    multi_valued = _assert_rule_has_id(composite_children[0])
    multi_valued_children = _as_list(multi_valued["rules"])
    _assert_rule_has_id(multi_valued_children[0])
    nested_composite = _assert_rule_has_id(multi_valued_children[1])
    _assert_rule_has_id(_as_list(nested_composite["rules"])[0])
    assumption_set = _assert_rule_has_id(composite_children[1])
    assumption = _as_dict(_as_list(assumption_set["assumptions"])[0])
    _assert_rule_has_id(assumption["rule"])

    conditional = _assert_rule_has_id(rules[1])
    if_composite = _assert_rule_has_id(_as_list(conditional["if_rules"])[0])
    _assert_rule_has_id(_as_list(if_composite["rules"])[0])
    then_multi_valued = _assert_rule_has_id(_as_list(conditional["then_rules"])[0])
    _assert_rule_has_id(_as_list(then_multi_valued["rules"])[0])
    else_assumption_set = _assert_rule_has_id(_as_list(conditional["else_rules"])[0])
    else_assumption = _as_dict(_as_list(else_assumption_set["assumptions"])[0])
    _assert_rule_has_id(else_assumption["rule"])

    multi_assumption_set = _assert_rule_has_id(rules[2])
    multi_assumption = _as_dict(_as_list(multi_assumption_set["assumptions"])[0])
    nested_conditional = _assert_rule_has_id(_as_list(multi_assumption["rules"])[0])
    _assert_rule_has_id(_as_list(nested_conditional["if_rules"])[0])
    _assert_rule_has_id(_as_list(nested_conditional["then_rules"])[0])
