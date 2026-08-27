"""add coach registration fields

Revision ID: d4e8f1a2b3c5
Revises: bf1468d0858b
Create Date: 2026-08-27 13:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e8f1a2b3c5"
down_revision: str | Sequence[str] | None = "bf1468d0858b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add username and email verification columns to users."""
    op.add_column("users", sa.Column("username", sa.String(length=30), nullable=True))
    op.add_column("users", sa.Column("confirmation_token", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("confirmation_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    """Remove coach registration columns from users."""
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "confirmation_sent_at")
    op.drop_column("users", "confirmation_token")
    op.drop_column("users", "username")
