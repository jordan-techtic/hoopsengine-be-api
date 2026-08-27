"""add coach registration fields

Revision ID: d4e8f1a2b3c5
Revises: bf1468d0858b
Create Date: 2026-08-27 13:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "d4e8f1a2b3c5"
down_revision: str | Sequence[str] | None = "bf1468d0858b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _users_column_names(connection) -> set[str]:
    """Return existing column names on users (create_managed_tables may pre-create some)."""
    return {column["name"] for column in inspect(connection).get_columns("users")}


def _users_index_names(connection) -> set[str]:
    """Return existing index names on users."""
    return {index["name"] for index in inspect(connection).get_indexes("users")}


def upgrade() -> None:
    """Add username and email verification columns to users."""
    connection = op.get_bind()
    existing_columns = _users_column_names(connection)
    existing_indexes = _users_index_names(connection)

    if "username" not in existing_columns:
        op.add_column("users", sa.Column("username", sa.String(length=30), nullable=True))
    if "confirmation_token" not in existing_columns:
        op.add_column("users", sa.Column("confirmation_token", sa.String(length=255), nullable=True))
    if "confirmation_sent_at" not in existing_columns:
        op.add_column(
            "users",
            sa.Column("confirmation_sent_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "terms_accepted_at" not in existing_columns:
        op.add_column(
            "users",
            sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        )

    index_name = op.f("ix_users_username")
    if index_name not in existing_indexes:
        op.create_index(index_name, "users", ["username"], unique=True)


def downgrade() -> None:
    """Remove coach registration columns from users."""
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "confirmation_sent_at")
    op.drop_column("users", "confirmation_token")
    op.drop_column("users", "username")
