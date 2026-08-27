"""Business logic for team roster search on the Practice Plans screen."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.services import client_db

logger = logging.getLogger(__name__)

PLAYERS_TABLE = "players"


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


async def _jersey_column_exists(db: AsyncSession) -> bool:
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'players'
                  AND column_name = 'jersey_number'
            )
            """
        )
    )
    return bool(exists)


async def _active_column_exists(db: AsyncSession) -> bool:
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'players'
                  AND column_name = 'active'
            )
            """
        )
    )
    return bool(exists)


async def search_team_roster(
    db: AsyncSession,
    user: User,
    query: str | None,
) -> dict[str, Any]:
    """Search active players in the user's organization by name or jersey number."""
    cleaned = _validate_search_query(query)

    if user.org_id is None:
        return {
            "success": True,
            "message": "No players matched your search",
            "status": "ready",
            "description": "Matching team roster players",
            "link": None,
            "error": None,
            "players": [],
        }

    await client_db.require_table(db, PLAYERS_TABLE)

    jersey_column_exists = await _jersey_column_exists(db)
    active_column_exists = await _active_column_exists(db)
    active_sql = "AND p.active = true" if active_column_exists else ""
    jersey_select = "p.jersey_number" if jersey_column_exists else "NULL AS jersey_number"
    jersey_filter = (
        "OR p.jersey_number ILIKE :pattern"
        if jersey_column_exists
        else ""
    )
    pattern = f"%{cleaned}%"

    result = await db.execute(
        text(
            f"""
            SELECT
                p.id,
                p.first_name,
                p.last_name,
                {jersey_select}
            FROM players p
            WHERE p.org_id = :org_id
              {active_sql}
              AND (
                    p.first_name ILIKE :pattern
                 OR p.last_name ILIKE :pattern
                 OR TRIM(CONCAT(p.first_name, ' ', p.last_name)) ILIKE :pattern
                 {jersey_filter}
              )
            ORDER BY p.last_name ASC, p.first_name ASC
            LIMIT 50
            """
        ),
        {"org_id": user.org_id, "pattern": pattern},
    )

    players = [
        {
            "id": UUID(str(row["id"])),
            "first_name": str(row["first_name"]),
            "last_name": str(row["last_name"]),
            "name": f"{row['first_name']} {row['last_name']}".strip(),
            "jersey_number": (
                str(row["jersey_number"]) if row.get("jersey_number") is not None else None
            ),
        }
        for row in result.mappings().all()
    ]

    logger.info(
        "Roster search for %r in org %s returned %d players",
        cleaned,
        user.org_id,
        len(players),
    )
    return {
        "success": True,
        "message": "Players found" if players else "No players matched your search",
        "status": "ready",
        "description": "Matching team roster players",
        "link": None,
        "error": None,
        "players": players,
    }
