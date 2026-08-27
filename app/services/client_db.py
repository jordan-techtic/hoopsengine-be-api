"""Shared helpers for client-domain PostgreSQL tables."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException

PRACTICE_SESSIONS_TABLE = "practice_sessions"


async def table_exists(db: AsyncSession, table_name: str) -> bool:
    """Return True when ``public.{table_name}`` exists.

    The table name is bound as a parameter — never interpolated into SQL.
    """
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table_name
            )
            """
        ),
        {"table_name": table_name},
    )
    return bool(exists)


async def require_table(db: AsyncSession, table_name: str) -> None:
    """Raise when a required client table is absent from the database."""
    if not await table_exists(db, table_name):
        raise AppException(
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Session recording is temporarily unavailable",
            status_code=503,
        )
