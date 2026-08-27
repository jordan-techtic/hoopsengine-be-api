"""Add phone column to support_requests_staging."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

from app.core.tables import SUPPORT_REQUESTS_TABLE

revision: str = "h1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "g3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(connection, table_name: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table_name)}


def upgrade() -> None:
    connection = op.get_bind()
    existing_columns = _column_names(connection, SUPPORT_REQUESTS_TABLE)
    if "phone" not in existing_columns:
        op.add_column(
            SUPPORT_REQUESTS_TABLE,
            sa.Column("phone", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    connection = op.get_bind()
    existing_columns = _column_names(connection, SUPPORT_REQUESTS_TABLE)
    if "phone" in existing_columns:
        op.drop_column(SUPPORT_REQUESTS_TABLE, "phone")
