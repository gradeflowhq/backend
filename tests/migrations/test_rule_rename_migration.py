import runpy
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

import sqlalchemy as sa
import yaml

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "migrations"
    / "versions"
    / "4c9b1a7d8e2f_rename_custom_code_and_code_tests_rules.py"
)


def _migration_namespace() -> dict[str, Any]:
    return runpy.run_path(str(MIGRATION_PATH))


def _rename_rubric_yaml(
    rubric_yaml: str,
    *,
    type_renames: Mapping[str, str],
    display_renames: Mapping[str, str],
) -> str | None:
    namespace = _migration_namespace()
    rename = cast(Callable[..., str | None], namespace["_rename_rubric_yaml"])
    return rename(
        rubric_yaml,
        type_renames=type_renames,
        display_renames=display_renames,
    )


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


def _upgrade_rubric_yaml(rubric_yaml: str) -> str | None:
    namespace = _migration_namespace()
    return _rename_rubric_yaml(
        rubric_yaml,
        type_renames=cast(dict[str, str], namespace["UPGRADE_TYPE_RENAMES"]),
        display_renames=cast(dict[str, str], namespace["UPGRADE_DISPLAY_RENAMES"]),
    )


def _downgrade_rubric_yaml(rubric_yaml: str) -> str | None:
    namespace = _migration_namespace()
    return _rename_rubric_yaml(
        rubric_yaml,
        type_renames=cast(dict[str, str], namespace["DOWNGRADE_TYPE_RENAMES"]),
        display_renames=cast(dict[str, str], namespace["DOWNGRADE_DISPLAY_RENAMES"]),
    )


def _rename_submission_result_rules(
    connection: sa.engine.Connection,
    display_renames: Mapping[str, str],
) -> None:
    namespace = _migration_namespace()
    rename = cast(
        Callable[[sa.engine.Connection, Mapping[str, str]], None],
        namespace["_rename_submission_result_rules"],
    )
    rename(connection, display_renames)


def test_rename_rubric_yaml_upgrades_rule_names_in_all_rule_container_shapes() -> None:
    renamed = _upgrade_rubric_yaml(
        """
rules:
  - type: PROGRAMMABLE
    display_name: Programmable
    name: Programmable
  - type: PROGRAMMABLE_MULTI
    display_name: Programmable
    name: Programmable
  - type: COMPOSITE
    rules:
      - type: PROGRAMMING
        display_name: Programming
        testcases:
          - expression: f()
            expected: '1'
  - type: CONDITIONAL
    if_rules:
      - type: PROGRAMMABLE
    then_rules:
      - type: PROGRAMMING
    else_rules: []
  - type: ASSUMPTION_SET
    assumptions:
      - rule:
          type: PROGRAMMING
          name: Programming
  - type: ASSUMPTION_SET_MULTI
    assumptions:
      - rules:
          - type: PROGRAMMABLE
            display_name: Programmable
"""
    )

    assert renamed is not None
    data = _load_yaml(renamed)
    rules = _as_list(data["rules"])

    assert _as_dict(rules[0])["type"] == "CUSTOM_CODE"
    assert _as_dict(rules[0])["display_name"] == "Custom Code"
    assert _as_dict(rules[0])["name"] == "Custom Code"
    assert _as_dict(rules[1])["type"] == "CUSTOM_CODE_MULTI"
    assert _as_dict(rules[1])["display_name"] == "Custom Code"
    assert _as_dict(rules[1])["name"] == "Custom Code"

    composite_child = _as_dict(_as_list(_as_dict(rules[2])["rules"])[0])
    assert composite_child["type"] == "CODE_TESTS"
    assert composite_child["display_name"] == "Code Tests"

    conditional = _as_dict(rules[3])
    assert _as_dict(_as_list(conditional["if_rules"])[0])["type"] == "CUSTOM_CODE"
    assert _as_dict(_as_list(conditional["then_rules"])[0])["type"] == "CODE_TESTS"

    assumption = _as_dict(_as_list(_as_dict(rules[4])["assumptions"])[0])
    assumption_rule = _as_dict(assumption["rule"])
    assert assumption_rule["type"] == "CODE_TESTS"
    assert assumption_rule["name"] == "Code Tests"

    multi_assumption = _as_dict(_as_list(_as_dict(rules[5])["assumptions"])[0])
    multi_assumption_rule = _as_dict(_as_list(multi_assumption["rules"])[0])
    assert multi_assumption_rule["type"] == "CUSTOM_CODE"
    assert multi_assumption_rule["display_name"] == "Custom Code"


def test_rename_rubric_yaml_returns_none_when_no_legacy_names_exist() -> None:
    assert (
        _upgrade_rubric_yaml(
            """
rules:
  - type: CUSTOM_CODE
    display_name: Custom Code
"""
        )
        is None
    )


def test_rename_rubric_yaml_downgrades_new_rule_names() -> None:
    renamed = _downgrade_rubric_yaml(
        """
rules:
  - type: CUSTOM_CODE
    display_name: Custom Code
  - type: CUSTOM_CODE_MULTI
    display_name: Custom Code
  - type: CODE_TESTS
    display_name: Code Tests
"""
    )

    assert renamed is not None
    rules = _as_list(_load_yaml(renamed)["rules"])
    assert _as_dict(rules[0]) == {"type": "PROGRAMMABLE", "display_name": "Programmable"}
    assert _as_dict(rules[1]) == {
        "type": "PROGRAMMABLE_MULTI",
        "display_name": "Programmable",
    }
    assert _as_dict(rules[2]) == {"type": "PROGRAMMING", "display_name": "Programming"}


def test_rename_submission_result_rules_updates_submission_results_table() -> None:
    namespace = _migration_namespace()
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    submission_results = sa.Table(
        "submission_results",
        metadata,
        sa.Column("rule", sa.String(), nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            submission_results.insert(),
            [
                {"rule": "Programmable"},
                {"rule": "Programmable (Multi)"},
                {"rule": "Programming"},
                {"rule": "Unchanged"},
            ],
        )

        _rename_submission_result_rules(
            connection,
            cast(dict[str, str], namespace["UPGRADE_DISPLAY_RENAMES"]),
        )

        rules = list(connection.execute(sa.select(submission_results.c.rule)).scalars())

    assert sorted(rules) == ["Code Tests", "Custom Code", "Custom Code", "Unchanged"]
