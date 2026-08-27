"""add session recording columns to practice_sessions

Revision ID: e1f2a3b4c5d6
Revises: 5a0d230693b5
Create Date: 2026-08-27 14:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "5a0d230693b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(connection, table_name: str) -> set[str]:
    """Return existing column names on a table, or empty set when table is absent."""
    inspector = inspect(connection)
    if table_name not in inspector.get_table_names(schema="public"):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name, schema="public")}


def _index_names(connection, table_name: str) -> set[str]:
    """Return existing index names on a table, or empty set when table is absent."""
    inspector = inspect(connection)
    if table_name not in inspector.get_table_names(schema="public"):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name, schema="public")}


def upgrade() -> None:
    """Extend practice_sessions with session recording fields."""
    connection = op.get_bind()
    columns = _column_names(connection, "practice_sessions")
    if not columns:
        return

    if "session_mode" not in columns:
        op.add_column("practice_sessions", sa.Column("session_mode", sa.Text(), nullable=True))
    if "session_details" not in columns:
        op.add_column(
            "practice_sessions",
            sa.Column("session_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    if "recorder_user_id" not in columns:
        op.add_column(
            "practice_sessions",
            sa.Column("recorder_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if "status" not in columns:
        op.add_column(
            "practice_sessions",
            sa.Column("status", sa.Text(), nullable=True, server_default="in_progress"),
        )
    if "started_at" not in columns:
        op.add_column(
            "practice_sessions",
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "ended_at" not in columns:
        op.add_column(
            "practice_sessions",
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "current_drill_index" not in columns:
        op.add_column(
            "practice_sessions",
            sa.Column("current_drill_index", sa.Integer(), nullable=True, server_default="0"),
        )
    if "practice_plan_id" not in columns:
        op.add_column(
            "practice_sessions",
            sa.Column("practice_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        )

    indexes = _index_names(connection, "practice_sessions")
    index_name = "ix_practice_sessions_recorder_user_id"
    if index_name not in indexes:
        op.create_index(index_name, "practice_sessions", ["recorder_user_id"], unique=False)


def downgrade() -> None:
    """Remove session recording columns from practice_sessions."""
    connection = op.get_bind()
    columns = _column_names(connection, "practice_sessions")
    if not columns:
        return

    indexes = _index_names(connection, "practice_sessions")
    if "ix_practice_sessions_recorder_user_id" in indexes:
        op.drop_index("ix_practice_sessions_recorder_user_id", table_name="practice_sessions")

    for column in (
        "practice_plan_id",
        "current_drill_index",
        "ended_at",
        "started_at",
        "status",
        "recorder_user_id",
        "session_details",
        "session_mode",
    ):
        if column in columns:
            op.drop_column("practice_sessions", column)
