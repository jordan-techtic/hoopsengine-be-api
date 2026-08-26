"""
Bootstrap schema on the target Hoops Engine DB (empty or partial).

Creates:
  1) Client domain tables from docs/sql/hoops_engine_client_schema.sql
  2) App-managed tables (`users` + other managed tables) via SQLAlchemy
  3) Subscription column/constraint migrations

Does NOT copy data and does NOT modify the source/staging database.

Usage (PowerShell):
  $env:DATABASE_URL="postgresql+asyncpg://.../hoops-engine-db"
  python scripts/bootstrap_hoops_engine_db.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.core.database import Base, create_managed_tables
from app.core.schema_migrations import run_subscription_schema_migrations
from app.models import (  # noqa: F401 — register metadata
    Organization,
    RevokedToken,
    StripeSubscription,
    SubscriptionPlan,
    SupportRequest,
    User,
)
from scripts.db_migration_lib import (
    CLIENT_SCHEMA_SQL,
    create_engine,
    database_label,
    resolve_database_url,
    split_sql_statements,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def apply_client_schema(engine) -> None:
    sql = CLIENT_SCHEMA_SQL.read_text(encoding="utf-8")
    statements = split_sql_statements(sql)
    async with engine.begin() as connection:
        for stmt in statements:
            await connection.execute(text(stmt))
    logger.info("Applied client schema (%s statements) from %s", len(statements), CLIENT_SCHEMA_SQL)


async def apply_managed_schema(engine) -> None:
    async with engine.begin() as connection:
        await run_subscription_schema_migrations(connection)
        await connection.run_sync(create_managed_tables)
    logger.info("Created/verified app-managed tables")


async def main() -> None:
    target_url = resolve_database_url(role="target")
    logger.info("Bootstrapping target DB: %s", database_label(target_url))

    engine = create_engine(target_url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        if not CLIENT_SCHEMA_SQL.exists():
            raise SystemExit(f"Missing schema file: {CLIENT_SCHEMA_SQL}")

        await apply_client_schema(engine)
        # Ensure metadata is loaded before create_all
        _ = Base.metadata
        await apply_managed_schema(engine)
        logger.info("Bootstrap complete for %s", database_label(target_url))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
