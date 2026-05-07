"""add assessment metadata

Revision ID: 9b8a7c6d5e4f
Revises: e4d4a97cb7af
Create Date: 2026-05-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b8a7c6d5e4f"
down_revision: str | Sequence[str] | None = "e4d4a97cb7af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("assessments", sa.Column("metadata", sa.JSON(), nullable=True))
    op.execute("UPDATE assessments SET metadata = '{}' WHERE metadata IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("assessments", "metadata")
