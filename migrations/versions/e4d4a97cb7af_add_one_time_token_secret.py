"""add one-time token secret

Revision ID: e4d4a97cb7af
Revises: 70aa69110e7a
Create Date: 2026-04-29 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4d4a97cb7af"
down_revision: str | Sequence[str] | None = "70aa69110e7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "one_time_tokens",
        sa.Column("secret", sa.String(length=128), nullable=True),
    )
    op.execute("UPDATE one_time_tokens SET secret = token WHERE secret IS NULL")
    op.alter_column(
        "one_time_tokens",
        "secret",
        nullable=False,
        existing_type=sa.String(length=128),
    )


def downgrade() -> None:
    op.drop_column("one_time_tokens", "secret")
