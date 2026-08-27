"""add active column to practice_plans

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-27 14:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(connection, table_name: str) -> set[str]:
    """Return existing column names on a table, or empty set when table is absent."""
    inspector = inspect(connection)
    if table_name not in inspector.get_table_names(schema="public"):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name, schema="public")}


def upgrade() -> None:
    """Add active flag to practice_plans for soft deletion."""
    connection = op.get_bind()
    columns = _column_names(connection, "practice_plans")
    if not columns:
        return

    if "active" not in columns:
        op.add_column(
            "practice_plans",
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )


def downgrade() -> None:
    """Remove active flag from practice_plans."""
    connection = op.get_bind()
    columns = _column_names(connection, "practice_plans")
    if not columns:
        return

    if "active" in columns:
        op.drop_column("practice_plans", "active")
