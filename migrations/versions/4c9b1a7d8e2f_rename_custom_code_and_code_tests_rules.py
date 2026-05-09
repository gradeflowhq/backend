"""rename custom code and code tests rules

Revision ID: 4c9b1a7d8e2f
Revises: 2d8f9c1a7b3e
Create Date: 2026-05-09 00:00:00.000000

"""

from collections.abc import Mapping, Sequence
from typing import Any, cast

import sqlalchemy as sa
import yaml
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c9b1a7d8e2f"
down_revision: str | Sequence[str] | None = "2d8f9c1a7b3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULE_LIST_FIELDS = ("rules", "if_rules", "then_rules", "else_rules")

UPGRADE_TYPE_RENAMES = {
    "PROGRAMMABLE": "CUSTOM_CODE",
    "PROGRAMMABLE_MULTI": "CUSTOM_CODE_MULTI",
    "PROGRAMMING": "CODE_TESTS",
}
UPGRADE_DISPLAY_RENAMES = {
    "Programmable": "Custom Code",
    "Programmable (Multi)": "Custom Code",
    "Programming": "Code Tests",
}

DOWNGRADE_TYPE_RENAMES = {new: old for old, new in UPGRADE_TYPE_RENAMES.items()}
DOWNGRADE_DISPLAY_RENAMES = {
    "Custom Code": "Programmable",
    "Code Tests": "Programming",
}


def _rename_value(
    data: dict[str, Any],
    field_name: str,
    renames: Mapping[str, str],
) -> bool:
    value = data.get(field_name)
    if not isinstance(value, str) or value not in renames:
        return False
    data[field_name] = renames[value]
    return True


def _rename_rule(
    rule: object,
    *,
    type_renames: Mapping[str, str],
    display_renames: Mapping[str, str],
) -> bool:
    if not isinstance(rule, dict):
        return False

    rule_data = cast(dict[str, Any], rule)
    changed = _rename_value(rule_data, "type", type_renames)
    changed = _rename_value(rule_data, "display_name", display_renames) or changed
    changed = _rename_value(rule_data, "name", display_renames) or changed

    for field_name in RULE_LIST_FIELDS:
        children = rule_data.get(field_name)
        if isinstance(children, list):
            for child in children:
                changed = (
                    _rename_rule(
                        child,
                        type_renames=type_renames,
                        display_renames=display_renames,
                    )
                    or changed
                )

    assumptions = rule_data.get("assumptions")
    if isinstance(assumptions, list):
        for assumption in assumptions:
            if not isinstance(assumption, dict):
                continue

            assumption_data = cast(dict[str, Any], assumption)
            changed = (
                _rename_rule(
                    assumption_data.get("rule"),
                    type_renames=type_renames,
                    display_renames=display_renames,
                )
                or changed
            )

            rules = assumption_data.get("rules")
            if isinstance(rules, list):
                for nested_rule in rules:
                    changed = (
                        _rename_rule(
                            nested_rule,
                            type_renames=type_renames,
                            display_renames=display_renames,
                        )
                        or changed
                    )

    return changed


def _rename_rubric_yaml(
    rubric_yaml: str,
    *,
    type_renames: Mapping[str, str],
    display_renames: Mapping[str, str],
) -> str | None:
    rubric = cast(object, yaml.safe_load(rubric_yaml))
    if not isinstance(rubric, dict):
        return None

    rubric_data = cast(dict[str, Any], rubric)
    rules = rubric_data.get("rules")
    if not isinstance(rules, list):
        return None

    changed = False
    for rule in rules:
        changed = (
            _rename_rule(rule, type_renames=type_renames, display_renames=display_renames)
            or changed
        )

    if not changed:
        return None
    return yaml.safe_dump(rubric_data, sort_keys=False, allow_unicode=True)


def _rename_assessment_rubrics(
    connection: sa.engine.Connection,
    *,
    type_renames: Mapping[str, str],
    display_renames: Mapping[str, str],
) -> None:
    rows = connection.execute(
        sa.text(
            """
            select id, rubric_yaml
            from assessments
            where rubric_yaml is not null
              and rubric_yaml <> ''
            """
        )
    )

    for assessment_id, rubric_yaml in rows:
        renamed = _rename_rubric_yaml(
            str(rubric_yaml),
            type_renames=type_renames,
            display_renames=display_renames,
        )
        if renamed is None:
            continue
        connection.execute(
            sa.text(
                """
                update assessments
                set rubric_yaml = :rubric_yaml
                where id = :assessment_id
                """
            ),
            {"assessment_id": assessment_id, "rubric_yaml": renamed},
        )


def _rename_submission_result_rules(
    connection: sa.engine.Connection,
    display_renames: Mapping[str, str],
) -> None:
    for old_name, new_name in display_renames.items():
        connection.execute(
            sa.text(
                """
                update submission_results
                set rule = :new_name
                where rule = :old_name
                """
            ),
            {"old_name": old_name, "new_name": new_name},
        )


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    _rename_assessment_rubrics(
        connection,
        type_renames=UPGRADE_TYPE_RENAMES,
        display_renames=UPGRADE_DISPLAY_RENAMES,
    )
    _rename_submission_result_rules(connection, UPGRADE_DISPLAY_RENAMES)


def downgrade() -> None:
    """Downgrade schema."""
    connection = op.get_bind()
    _rename_assessment_rubrics(
        connection,
        type_renames=DOWNGRADE_TYPE_RENAMES,
        display_renames=DOWNGRADE_DISPLAY_RENAMES,
    )
    _rename_submission_result_rules(connection, DOWNGRADE_DISPLAY_RENAMES)
