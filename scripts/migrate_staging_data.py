"""
Copy selected table data from staging DB → target Hoops Engine DB.

- Source is READ-ONLY (never truncated/altered).
- Target must already have schema (run bootstrap_hoops_engine_db.py first).
- Default table set keeps auth/API + drills/orgs/subscriptions working.
- Idempotent: ON CONFLICT (primary key) DO NOTHING.

Usage (PowerShell):
  $env:SOURCE_DATABASE_URL="postgresql+asyncpg://.../hoops-engine-db-staging"
  $env:TARGET_DATABASE_URL="postgresql+asyncpg://.../hoops-engine-db"
  python scripts/migrate_staging_data.py

  # Include practice history / empty structural tables:
  python scripts/migrate_staging_data.py --include-optional

  # Replace existing rows on target for selected tables:
  python scripts/migrate_staging_data.py --replace

  # Dry run (counts only):
  python scripts/migrate_staging_data.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from scripts.db_migration_lib import (
    DEFAULT_DATA_TABLES,
    OPTIONAL_DATA_TABLES,
    create_engine,
    database_label,
    ordered_tables,
    resolve_database_url,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 200

# Source DB may still use legacy names while target uses canonical names.
SOURCE_TABLE_ALIASES: dict[str, tuple[str, ...]] = {
    "users": ("users", "users_staging", "users_he"),
}


async def resolve_source_table(
    connection: AsyncConnection, logical_name: str
) -> str | None:
    candidates = SOURCE_TABLE_ALIASES.get(logical_name, (logical_name,))
    for name in candidates:
        if await table_exists(connection, name):
            return name
    return None


async def table_exists(connection: AsyncConnection, table_name: str) -> bool:
    return bool(
        await connection.scalar(
            text(
                """
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.tables
                  WHERE table_schema = 'public' AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        )
    )


async def primary_key_columns(connection: AsyncConnection, table_name: str) -> list[str]:
    rows = (
        await connection.execute(
            text(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = 'public'
                  AND tc.table_name = :table_name
                  AND tc.constraint_type = 'PRIMARY KEY'
                ORDER BY kcu.ordinal_position
                """
            ),
            {"table_name": table_name},
        )
    ).fetchall()
    return [row[0] for row in rows]


async def column_names(connection: AsyncConnection, table_name: str) -> list[str]:
    rows = (
        await connection.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table_name
                ORDER BY ordinal_position
                """
            ),
            {"table_name": table_name},
        )
    ).fetchall()
    return [row[0] for row in rows]


async def column_udt_map(connection: AsyncConnection, table_name: str) -> dict[str, str]:
    rows = (
        await connection.execute(
            text(
                """
                SELECT column_name, udt_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table_name
                """
            ),
            {"table_name": table_name},
        )
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def bind_value(value: Any, udt_name: str) -> Any:
    """Serialize values so asyncpg + raw SQL can bind JSON/array columns."""
    if value is None:
        return None
    if udt_name in {"json", "jsonb"}:
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value
    return value


async def fetch_all_rows(
    connection: AsyncConnection, table_name: str, columns: list[str]
) -> list[dict[str, Any]]:
    col_sql = ", ".join(f'"{c}"' for c in columns)
    result = await connection.execute(text(f'SELECT {col_sql} FROM public."{table_name}"'))
    return [dict(row._mapping) for row in result]


async def truncate_table(connection: AsyncConnection, table_name: str) -> None:
    await connection.execute(
        text(f'TRUNCATE TABLE public."{table_name}" RESTART IDENTITY CASCADE')
    )


async def insert_batch(
    connection: AsyncConnection,
    *,
    table_name: str,
    columns: list[str],
    pk_cols: list[str],
    rows: list[dict[str, Any]],
    udt_map: dict[str, str] | None = None,
) -> int:
    if not rows:
        return 0

    udt_map = udt_map or {}
    col_sql = ", ".join(f'"{c}"' for c in columns)
    placeholder_parts: list[str] = []
    for col in columns:
        udt = udt_map.get(col, "")
        if udt in {"json", "jsonb"}:
            placeholder_parts.append(f"CAST(:{col} AS {udt})")
        else:
            placeholder_parts.append(f":{col}")
    placeholders = ", ".join(placeholder_parts)
    conflict = ", ".join(f'"{c}"' for c in pk_cols) if pk_cols else ""

    if conflict:
        sql = (
            f'INSERT INTO public."{table_name}" ({col_sql}) '
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict}) DO NOTHING"
        )
    else:
        sql = f'INSERT INTO public."{table_name}" ({col_sql}) VALUES ({placeholders})'

    inserted = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        for row in batch:
            payload = {
                col: bind_value(row.get(col), udt_map.get(col, ""))
                for col in columns
            }
            result = await connection.execute(text(sql), payload)
            inserted += result.rowcount or 0
    return inserted


async def copy_subscription_plans(
    source: AsyncConnection,
    target: AsyncConnection,
    *,
    replace: bool,
    dry_run: bool,
) -> tuple[int, int]:
    """Two-pass copy so self-FK replacement_plan_id cannot fail mid-insert."""
    table = "subscription_plans_staging"
    columns = await column_names(source, table)
    target_columns = await column_names(target, table)
    columns = [c for c in columns if c in set(target_columns)]
    pk_cols = await primary_key_columns(target, table)
    udt_map = await column_udt_map(target, table)
    rows = await fetch_all_rows(source, table, columns)
    source_count = len(rows)

    if dry_run:
        return source_count, 0

    if replace:
        await truncate_table(target, table)

    pass1_cols = [c for c in columns if c != "replacement_plan_id"]
    pass1_rows = []
    for row in rows:
        cleaned = {c: row.get(c) for c in pass1_cols}
        pass1_rows.append(cleaned)

    inserted = await insert_batch(
        target,
        table_name=table,
        columns=pass1_cols,
        pk_cols=pk_cols,
        rows=pass1_rows,
        udt_map=udt_map,
    )

    if "replacement_plan_id" in columns:
        for row in rows:
            if row.get("replacement_plan_id") is None:
                continue
            await target.execute(
                text(
                    """
                    UPDATE public.subscription_plans_staging
                    SET replacement_plan_id = :replacement_plan_id
                    WHERE id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "replacement_plan_id": row["replacement_plan_id"],
                },
            )

    return source_count, inserted


async def copy_table(
    source: AsyncConnection,
    target: AsyncConnection,
    table_name: str,
    *,
    replace: bool,
    dry_run: bool,
) -> tuple[int, int]:
    source_table = await resolve_source_table(source, table_name)
    if source_table is None:
        logger.warning("Skip %s — missing on source", table_name)
        return 0, 0
    if not await table_exists(target, table_name):
        logger.warning("Skip %s — missing on target (run bootstrap first)", table_name)
        return 0, 0
    if source_table != table_name:
        logger.info("Source alias: %s → target %s", source_table, table_name)

    if table_name == "subscription_plans_staging":
        return await copy_subscription_plans(
            source, target, replace=replace, dry_run=dry_run
        )

    source_cols = await column_names(source, source_table)
    target_cols = set(await column_names(target, table_name))
    columns = [c for c in source_cols if c in target_cols]
    skipped_cols = [c for c in source_cols if c not in target_cols]
    if skipped_cols:
        logger.info("%s: ignoring source-only columns %s", table_name, skipped_cols)

    pk_cols = await primary_key_columns(target, table_name)
    udt_map = await column_udt_map(target, table_name)
    rows = await fetch_all_rows(source, source_table, columns)
    source_count = len(rows)

    if dry_run:
        return source_count, 0

    if replace:
        await truncate_table(target, table_name)

    inserted = await insert_batch(
        target,
        table_name=table_name,
        columns=columns,
        pk_cols=pk_cols,
        rows=rows,
        udt_map=udt_map,
    )
    return source_count, inserted


async def run(tables: list[str], *, replace: bool, dry_run: bool) -> None:
    source_url = resolve_database_url(role="source")
    target_url = resolve_database_url(role="target")

    if database_label(source_url) == database_label(target_url):
        raise SystemExit("SOURCE and TARGET database names must be different.")

    logger.info("Source (read-only): %s", database_label(source_url))
    logger.info("Target:             %s", database_label(target_url))
    logger.info("Tables: %s", ", ".join(tables))
    if dry_run:
        logger.info("DRY RUN — no writes")
    if replace:
        logger.info("REPLACE mode — truncate target tables before insert (CASCADE)")

    source_engine: AsyncEngine = create_engine(source_url)
    target_engine: AsyncEngine = create_engine(target_url)

    try:
        async with source_engine.connect() as source_conn:
            async with target_engine.begin() as target_conn:
                # Relax FK checks for load (superuser on DO usually allowed).
                if not dry_run:
                    await target_conn.execute(text("SET session_replication_role = replica"))

                for table in tables:
                    src_count, inserted = await copy_table(
                        source_conn,
                        target_conn,
                        table,
                        replace=replace,
                        dry_run=dry_run,
                    )
                    logger.info(
                        "%s: source=%s inserted_or_kept=%s",
                        table,
                        src_count,
                        "n/a (dry-run)" if dry_run else inserted,
                    )

                if not dry_run:
                    await target_conn.execute(text("SET session_replication_role = DEFAULT"))
    finally:
        await source_engine.dispose()
        await target_engine.dispose()

    logger.info("Migration finished")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate selected staging data to target DB")
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Also copy optional/history tables (session_data, trial_users, etc.)",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        help="Explicit table list (overrides defaults)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Truncate target table (CASCADE) before insert",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count source rows only; do not write",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.tables:
        selected = ordered_tables(args.tables)
    else:
        selected = list(DEFAULT_DATA_TABLES)
        if args.include_optional:
            selected = ordered_tables([*DEFAULT_DATA_TABLES, *OPTIONAL_DATA_TABLES])
        else:
            selected = ordered_tables(selected)

    asyncio.run(run(selected, replace=args.replace, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
