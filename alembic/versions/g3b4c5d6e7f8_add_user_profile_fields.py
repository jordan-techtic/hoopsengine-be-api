"""add coach profile fields to users

Revision ID: g3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-27 14:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "g3b4c5d6e7f8"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _users_column_names(connection) -> set[str]:
    """Return existing column names on users."""
    return {column["name"] for column in inspect(connection).get_columns("users")}


def upgrade() -> None:
    """Add extended profile columns to users."""
    connection = op.get_bind()
    existing_columns = _users_column_names(connection)

    if "date_of_birth" not in existing_columns:
        op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    if "gender" not in existing_columns:
        op.add_column("users", sa.Column("gender", sa.Text(), nullable=True))
    if "grade" not in existing_columns:
        op.add_column("users", sa.Column("grade", sa.Text(), nullable=True))
    if "parent_guardian" not in existing_columns:
        op.add_column("users", sa.Column("parent_guardian", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove extended profile columns from users."""
    connection = op.get_bind()
    existing_columns = _users_column_names(connection)

    for column in ("parent_guardian", "grade", "gender", "date_of_birth"):
        if column in existing_columns:
            op.drop_column("users", column)
