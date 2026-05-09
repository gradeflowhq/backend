"""assign missing rule ids

Revision ID: 2d8f9c1a7b3e
Revises: 9b8a7c6d5e4f
Create Date: 2026-05-09 00:00:00.000000

"""

from collections.abc import Sequence
from typing import Any, cast
from uuid import uuid4

import sqlalchemy as sa
import yaml
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2d8f9c1a7b3e"
down_revision: str | Sequence[str] | None = "9b8a7c6d5e4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULE_LIST_FIELDS = ("rules", "if_rules", "then_rules", "else_rules")


def _assign_missing_rule_ids(rule: object) -> bool:
    if not isinstance(rule, dict):
        return False

    rule_data = cast(dict[str, Any], rule)
    if not isinstance(rule_data.get("type"), str):
        return False

    changed = False
    rule_id = rule_data.get("id")
    if not isinstance(rule_id, str) or not rule_id:
        rule_data["id"] = uuid4().hex
        changed = True

    for field_name in RULE_LIST_FIELDS:
        children = rule_data.get(field_name)
        if isinstance(children, list):
            for child in children:
                changed = _assign_missing_rule_ids(child) or changed

    assumptions = rule_data.get("assumptions")
    if isinstance(assumptions, list):
        for assumption in assumptions:
            if not isinstance(assumption, dict):
                continue

            assumption_data = cast(dict[str, Any], assumption)
            changed = _assign_missing_rule_ids(assumption_data.get("rule")) or changed

            rules = assumption_data.get("rules")
            if isinstance(rules, list):
                for rule in rules:
                    changed = _assign_missing_rule_ids(rule) or changed

    return changed


def _normalize_rubric_yaml(rubric_yaml: str) -> str | None:
    rubric = cast(object, yaml.safe_load(rubric_yaml))
    if not isinstance(rubric, dict):
        return None

    rubric_data = cast(dict[str, Any], rubric)
    rules = rubric_data.get("rules")
    if not isinstance(rules, list):
        return None

    changed = False
    for rule in rules:
        changed = _assign_missing_rule_ids(rule) or changed

    if not changed:
        return None
    return yaml.safe_dump(rubric_data, sort_keys=False, allow_unicode=True)


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
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
        normalized = _normalize_rubric_yaml(str(rubric_yaml))
        if normalized is None:
            continue
        connection.execute(
            sa.text(
                """
                update assessments
                set rubric_yaml = :rubric_yaml
                where id = :assessment_id
                """
            ),
            {"assessment_id": assessment_id, "rubric_yaml": normalized},
        )


def downgrade() -> None:
    """Downgrade schema."""
    pass
