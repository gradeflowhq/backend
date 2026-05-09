"""add grading job completed at

Revision ID: c3f2a1b0d9e8
Revises: 4c9b1a7d8e2f
Create Date: 2026-05-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f2a1b0d9e8"
down_revision: str | Sequence[str] | None = "4c9b1a7d8e2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "grading_jobs",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_grading_jobs_type_completed_at",
        "grading_jobs",
        ["type", "completed_at"],
        unique=False,
    )
    op.create_index(
        "ix_grading_jobs_assessment_type_completed_at",
        "grading_jobs",
        ["assessment_id", "type", "completed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_grading_jobs_assessment_type_completed_at", table_name="grading_jobs")
    op.drop_index("ix_grading_jobs_type_completed_at", table_name="grading_jobs")
    op.drop_column("grading_jobs", "completed_at")
