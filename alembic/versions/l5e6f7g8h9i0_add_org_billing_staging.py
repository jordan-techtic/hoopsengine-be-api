"""Add org billing history and payment method staging tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.tables import ORG_BILLING_HISTORY_TABLE, ORG_PAYMENT_METHODS_TABLE

revision: str = "l5e6f7g8h9i0"
down_revision: str | Sequence[str] | None = "k4d5e6f7g8h9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(connection, table_name: str) -> bool:
    """Return True when the table already exists."""
    return table_name in inspect(connection).get_table_names(schema="public")


def upgrade() -> None:
    """Create org billing staging tables."""
    connection = op.get_bind()

    if not _table_exists(connection, ORG_BILLING_HISTORY_TABLE):
        op.create_table(
            ORG_BILLING_HISTORY_TABLE,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("billing_date", sa.Date(), nullable=False),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(length=8), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f(f"ix_{ORG_BILLING_HISTORY_TABLE}_org_id"),
            ORG_BILLING_HISTORY_TABLE,
            ["org_id"],
            unique=False,
        )

    if not _table_exists(connection, ORG_PAYMENT_METHODS_TABLE):
        op.create_table(
            ORG_PAYMENT_METHODS_TABLE,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("stripe_customer_id", sa.String(length=255), nullable=False),
            sa.Column("stripe_payment_method_id", sa.String(length=255), nullable=False),
            sa.Column("card_last4", sa.String(length=4), nullable=False),
            sa.Column("exp_month", sa.Integer(), nullable=False),
            sa.Column("exp_year", sa.Integer(), nullable=False),
            sa.Column("brand", sa.String(length=32), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("org_id"),
        )


def downgrade() -> None:
    """Drop org billing staging tables."""
    connection = op.get_bind()

    if _table_exists(connection, ORG_PAYMENT_METHODS_TABLE):
        op.drop_table(ORG_PAYMENT_METHODS_TABLE)

    if _table_exists(connection, ORG_BILLING_HISTORY_TABLE):
        op.drop_index(
            op.f(f"ix_{ORG_BILLING_HISTORY_TABLE}_org_id"),
            table_name=ORG_BILLING_HISTORY_TABLE,
        )
        op.drop_table(ORG_BILLING_HISTORY_TABLE)
