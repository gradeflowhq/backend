"""add grading job status and finished at

Revision ID: 8d12f9a4e6b7
Revises: c3f2a1b0d9e8
Create Date: 2026-05-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d12f9a4e6b7"
down_revision: str | Sequence[str] | None = "c3f2a1b0d9e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("ix_grading_jobs_assessment_type_completed_at", table_name="grading_jobs")
    op.drop_index("ix_grading_jobs_type_completed_at", table_name="grading_jobs")

    with op.batch_alter_table("grading_jobs") as batch_op:
        batch_op.alter_column(
            "completed_at",
            new_column_name="finished_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
        )
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'queued'"),
            )
        )
        batch_op.add_column(sa.Column("error", sa.Text(), nullable=True))

    op.execute("UPDATE grading_jobs SET status = 'completed' WHERE finished_at IS NOT NULL")

    op.create_index(
        "ix_grading_jobs_type_status_finished_at",
        "grading_jobs",
        ["type", "status", "finished_at"],
        unique=False,
    )
    op.create_index(
        "ix_grading_jobs_assessment_type_status_finished_at",
        "grading_jobs",
        ["assessment_id", "type", "status", "finished_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_grading_jobs_assessment_type_status_finished_at", table_name="grading_jobs")
    op.drop_index("ix_grading_jobs_type_status_finished_at", table_name="grading_jobs")

    op.execute("UPDATE grading_jobs SET finished_at = NULL WHERE status != 'completed'")

    with op.batch_alter_table("grading_jobs") as batch_op:
        batch_op.drop_column("error")
        batch_op.drop_column("status")
        batch_op.alter_column(
            "finished_at",
            new_column_name="completed_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=True,
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
