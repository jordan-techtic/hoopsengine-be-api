"""Shared helpers for Hoops Engine DB bootstrap / selective data migration."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
CLIENT_SCHEMA_SQL = ROOT / "docs" / "sql" / "hoops_engine_client_schema.sql"

# Client domain tables — create schema for all; migrate data for DEFAULT_DATA_TABLES.
CLIENT_SCHEMA_TABLES: tuple[str, ...] = (
    "organizations",
    "teams",
    "subteams",
    "coaches",
    "players",
    "drills",
    "subteam_drill_sets",
    "practice_plans",
    "practice_plan_drills",
    "drill_submissions",
    "session_codes",
    "practice_sessions",
    "session_data",
    "user_roles",
    "usernames",
    "trial_users",
)

# App-managed tables (SQLAlchemy). Schema created via create_all; data copied selectively.
MANAGED_DATA_TABLES: tuple[str, ...] = (
    "users",
    "subscription_plans_staging",
    "support_requests_staging",
    "stripe_subscriptions_staging",
)

# Safe default data set for a working API + product catalog (no auth.*, no token junk).
DEFAULT_DATA_TABLES: tuple[str, ...] = (
    "organizations",
    "teams",
    "drills",
    "players",
    "practice_plans",
    "practice_plan_drills",
    "user_roles",
    "usernames",
    "users",
    "subscription_plans_staging",
    "support_requests_staging",
    "stripe_subscriptions_staging",
)

# Optional history / rarely needed.
OPTIONAL_DATA_TABLES: tuple[str, ...] = (
    "subteams",
    "coaches",
    "subteam_drill_sets",
    "session_codes",
    "practice_sessions",
    "session_data",
    "drill_submissions",
    "trial_users",
    "revoked_tokens_staging",
)

# FK-safe copy order (parents before children).
COPY_ORDER: tuple[str, ...] = (
    "organizations",
    "teams",
    "subteams",
    "coaches",
    "players",
    "drills",
    "subteam_drill_sets",
    "practice_plans",
    "practice_plan_drills",
    "drill_submissions",
    "session_codes",
    "practice_sessions",
    "session_data",
    "user_roles",
    "usernames",
    "trial_users",
    "users",
    "subscription_plans_staging",
    "stripe_subscriptions_staging",
    "support_requests_staging",
    "revoked_tokens_staging",
)


def resolve_database_url(*, role: str) -> str:
    """
    role: 'source' | 'target'

    target: TARGET_DATABASE_URL or DATABASE_URL
    source: SOURCE_DATABASE_URL (required for migrate), never writes to source
    """
    if role == "target":
        url = os.getenv("TARGET_DATABASE_URL") or os.getenv("DATABASE_URL")
        if not url:
            raise SystemExit(
                "Set TARGET_DATABASE_URL or DATABASE_URL for the destination database."
            )
        return url

    if role == "source":
        url = os.getenv("SOURCE_DATABASE_URL")
        if not url:
            raise SystemExit(
                "Set SOURCE_DATABASE_URL to the staging DB "
                "(e.g. .../hoops-engine-db-staging). Source is read-only."
            )
        return url

    raise ValueError(f"Unknown role: {role}")


def database_label(url: str) -> str:
    parsed = make_url(url)
    return parsed.database or url


def create_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )


def ordered_tables(selected: Sequence[str]) -> list[str]:
    selected_set = set(selected)
    unknown = selected_set - set(COPY_ORDER)
    if unknown:
        raise SystemExit(f"Unknown table(s) in selection: {sorted(unknown)}")
    return [name for name in COPY_ORDER if name in selected_set]


def split_sql_statements(sql: str) -> list[str]:
    """Split a simple SQL file on semicolons (no procedure bodies in our schema file)."""
    statements: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                statements.append(stmt.rstrip(";").strip())
            buf = []
    trailing = "\n".join(buf).strip()
    if trailing:
        statements.append(trailing)
    return statements
