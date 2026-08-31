"""Add org UI design and feedback staging tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.tables import ORG_UI_DESIGN_FEEDBACK_TABLE, ORG_UI_DESIGNS_TABLE

revision: str = "k4d5e6f7g8h9"
down_revision: str | Sequence[str] | None = "j3c4d5e6f7g8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(connection, table_name: str) -> bool:
    """Return True when the table already exists."""
    return table_name in inspect(connection).get_table_names(schema="public")


def upgrade() -> None:
    """Create org UI design staging tables."""
    connection = op.get_bind()

    if not _table_exists(connection, ORG_UI_DESIGNS_TABLE):
        op.create_table(
            ORG_UI_DESIGNS_TABLE,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("template_name", sa.Text(), nullable=False),
            sa.Column("elements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
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
        )
        op.create_index(
            op.f(f"ix_{ORG_UI_DESIGNS_TABLE}_org_id"),
            ORG_UI_DESIGNS_TABLE,
            ["org_id"],
            unique=False,
        )

    if not _table_exists(connection, ORG_UI_DESIGN_FEEDBACK_TABLE):
        op.create_table(
            ORG_UI_DESIGN_FEEDBACK_TABLE,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("session_token", sa.String(length=64), nullable=False),
            sa.Column("design_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("feedback", sa.Text(), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f(f"ix_{ORG_UI_DESIGN_FEEDBACK_TABLE}_org_id"),
            ORG_UI_DESIGN_FEEDBACK_TABLE,
            ["org_id"],
            unique=False,
        )
        op.create_index(
            op.f(f"ix_{ORG_UI_DESIGN_FEEDBACK_TABLE}_session_token"),
            ORG_UI_DESIGN_FEEDBACK_TABLE,
            ["session_token"],
            unique=False,
        )


def downgrade() -> None:
    """Drop org UI design staging tables."""
    connection = op.get_bind()

    if _table_exists(connection, ORG_UI_DESIGN_FEEDBACK_TABLE):
        op.drop_index(
            op.f(f"ix_{ORG_UI_DESIGN_FEEDBACK_TABLE}_session_token"),
            table_name=ORG_UI_DESIGN_FEEDBACK_TABLE,
        )
        op.drop_index(
            op.f(f"ix_{ORG_UI_DESIGN_FEEDBACK_TABLE}_org_id"),
            table_name=ORG_UI_DESIGN_FEEDBACK_TABLE,
        )
        op.drop_table(ORG_UI_DESIGN_FEEDBACK_TABLE)

    if _table_exists(connection, ORG_UI_DESIGNS_TABLE):
        op.drop_index(
            op.f(f"ix_{ORG_UI_DESIGNS_TABLE}_org_id"),
            table_name=ORG_UI_DESIGNS_TABLE,
        )
        op.drop_table(ORG_UI_DESIGNS_TABLE)
