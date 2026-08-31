"""add description column to teams table

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
Create Date: 2026-08-31 16:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "n7o8p9q0r1s2"
down_revision: str | Sequence[str] | None = "m6n7o8p9q0r1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(connection, table_name: str) -> set[str]:
    """Return existing column names on a table, or empty set when table is absent."""
    inspector = inspect(connection)
    if table_name not in inspector.get_table_names(schema="public"):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name, schema="public")}


def upgrade() -> None:
    """Add description field for org-admin team content."""
    connection = op.get_bind()
    team_columns = _column_names(connection, "teams")
    if team_columns and "description" not in team_columns:
        op.add_column("teams", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove description field from teams table."""
    connection = op.get_bind()
    team_columns = _column_names(connection, "teams")
    if team_columns and "description" in team_columns:
        op.drop_column("teams", "description")
