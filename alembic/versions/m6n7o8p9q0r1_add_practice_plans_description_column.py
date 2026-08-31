"""add description columns to practice plan tables

Revision ID: m6n7o8p9q0r1
Revises: 312e76ed6d4e
Create Date: 2026-08-31 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "m6n7o8p9q0r1"
down_revision: str | Sequence[str] | None = "312e76ed6d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(connection, table_name: str) -> set[str]:
    """Return existing column names on a table, or empty set when table is absent."""
    inspector = inspect(connection)
    if table_name not in inspector.get_table_names(schema="public"):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name, schema="public")}


def upgrade() -> None:
    """Add description fields for org-admin practice plan content."""
    connection = op.get_bind()

    plan_columns = _column_names(connection, "practice_plans")
    if plan_columns and "description" not in plan_columns:
        op.add_column("practice_plans", sa.Column("description", sa.Text(), nullable=True))

    drill_columns = _column_names(connection, "practice_plan_drills")
    if drill_columns and "drill_description" not in drill_columns:
        op.add_column(
            "practice_plan_drills",
            sa.Column("drill_description", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    """Remove description fields from practice plan tables."""
    connection = op.get_bind()

    drill_columns = _column_names(connection, "practice_plan_drills")
    if drill_columns and "drill_description" in drill_columns:
        op.drop_column("practice_plan_drills", "drill_description")

    plan_columns = _column_names(connection, "practice_plans")
    if plan_columns and "description" in plan_columns:
        op.drop_column("practice_plans", "description")
