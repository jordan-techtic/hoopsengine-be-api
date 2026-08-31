"""Add org_reports_staging table for organization admin reports."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.tables import ORG_REPORTS_TABLE

revision: str = "i2b3c4d5e6f7_add_org_reports_staging"
down_revision: str | Sequence[str] | None = "807d5c5056ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(connection, table_name: str) -> bool:
    """Return True when the table already exists."""
    return table_name in inspect(connection).get_table_names(schema="public")


def upgrade() -> None:
    """Create org_reports_staging for persisted admin reports."""
    connection = op.get_bind()
    if _table_exists(connection, ORG_REPORTS_TABLE):
        return

    op.create_table(
        ORG_REPORTS_TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f(f"ix_{ORG_REPORTS_TABLE}_org_id"),
        ORG_REPORTS_TABLE,
        ["org_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop org_reports_staging."""
    connection = op.get_bind()
    if not _table_exists(connection, ORG_REPORTS_TABLE):
        return
    op.drop_index(op.f(f"ix_{ORG_REPORTS_TABLE}_org_id"), table_name=ORG_REPORTS_TABLE)
    op.drop_table(ORG_REPORTS_TABLE)
