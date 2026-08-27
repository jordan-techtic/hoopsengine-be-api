"""Business logic for drill search used by Edit Practice Plan."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.services import client_db

logger = logging.getLogger(__name__)

DRILLS_TABLE = "drills"


async def _approved_column_exists(db: AsyncSession) -> bool:
    """Return True when drills.approved exists."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'drills'
                  AND column_name = 'approved'
            )
            """
        )
    )
    return bool(exists)


def _validate_search_query(query: str | None) -> str:
    """Return a trimmed search query or raise 400 when empty."""
    cleaned = (query or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Search query is required",
            status_code=400,
            details=[{"field": "q", "message": "Search query cannot be empty"}],
        )
    return cleaned


async def search_drills(db: AsyncSession, query: str | None) -> dict[str, Any]:
    """Search active drills by name for the Edit Practice Plan drill picker."""
    cleaned = _validate_search_query(query)
    await client_db.require_table(db, DRILLS_TABLE)

    approved_column_exists = await _approved_column_exists(db)
    approved_sql = "AND d.approved = true" if approved_column_exists else ""
    pattern = f"%{cleaned}%"

    result = await db.execute(
        text(
            f"""
            SELECT d.id, d.name, d.category
            FROM drills d
            WHERE d.name ILIKE :pattern
              {approved_sql}
            ORDER BY d.name ASC
            LIMIT 50
            """
        ),
        {"pattern": pattern},
    )

    drills = [
        {
            "id": UUID(str(row["id"])),
            "name": str(row["name"]),
            "type": str(row["category"]),
        }
        for row in result.mappings().all()
    ]

    logger.info("Drill search for %r returned %d results", cleaned, len(drills))
    return {
        "success": True,
        "message": "Drills found" if drills else "No drills matched your search",
        "status": "ready",
        "description": "Matching active drills",
        "link": None,
        "error": None,
        "drills": drills,
    }
