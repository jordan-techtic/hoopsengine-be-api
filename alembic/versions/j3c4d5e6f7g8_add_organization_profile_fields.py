"""Add organization profile description and contact_info columns."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "j3c4d5e6f7g8"
down_revision: str | Sequence[str] | None = "i2b3c4d5e6f7_add_org_reports_staging"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _organizations_column_names(connection) -> set[str]:
    """Return existing column names on organizations."""
    return {column["name"] for column in inspect(connection).get_columns("organizations")}


def upgrade() -> None:
    """Add profile description and contact_info to organizations."""
    connection = op.get_bind()
    existing_columns = _organizations_column_names(connection)

    if "profile_description" not in existing_columns:
        op.add_column(
            "organizations",
            sa.Column("profile_description", sa.Text(), nullable=True),
        )
    if "contact_info" not in existing_columns:
        op.add_column(
            "organizations",
            sa.Column("contact_info", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    """Remove profile description and contact_info from organizations."""
    connection = op.get_bind()
    existing_columns = _organizations_column_names(connection)

    if "contact_info" in existing_columns:
        op.drop_column("organizations", "contact_info")
    if "profile_description" in existing_columns:
        op.drop_column("organizations", "profile_description")
