"""add role_selections table

Revision ID: i2j3k4l5m6n7
Revises: cd6841715b00
Create Date: 2026-08-27 15:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "i2j3k4l5m6n7"
down_revision: str | Sequence[str] | None = "cd6841715b00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create role_selections table for pre-registration role persistence."""
    op.create_table(
        "role_selections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selected_role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token"),
    )
    op.create_index(
        op.f("ix_role_selections_session_token"),
        "role_selections",
        ["session_token"],
        unique=True,
    )


def downgrade() -> None:
    """Drop role_selections table."""
    op.drop_index(op.f("ix_role_selections_session_token"), table_name="role_selections")
    op.drop_table("role_selections")
