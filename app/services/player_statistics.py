"""Business logic for public player statistics retrieval."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.services import client_db
from app.services.session_summary import (
    FREE_THROW_CATEGORY_PATTERN,
    compute_shooting_percent,
)

logger = logging.getLogger(__name__)

PLAYERS_TABLE = "players"
SESSION_DATA_TABLE = "session_data"
PRACTICE_SESSIONS_TABLE = "practice_sessions"


def parse_player_id(value: str) -> UUID:
    """Parse and validate a player_id path parameter."""
    cleaned = str(value).strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid player_id",
            status_code=400,
            details=[{"field": "player_id", "message": "player_id is required"}],
        )
    try:
        return UUID(cleaned)
    except ValueError as exc:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid player_id",
            status_code=400,
            details=[{"field": "player_id", "message": "player_id must be a valid UUID"}],
        ) from exc


def _format_display_date(value: datetime | None) -> str:
    """Format a session date for the statistics screen."""
    if value is None:
        return "Unknown Date"
    return value.strftime("%b %d, %Y")


def _format_performance(makes: int, attempts: int) -> str:
    """Format makes/attempts with percentage for session history rows."""
    percent = compute_shooting_percent(makes, attempts)
    return f"{makes}/{attempts} ({percent}%)"


def _format_shooting_percentage(makes: int, attempts: int) -> str:
    """Format aggregate shooting percentage with one decimal place."""
    if attempts <= 0:
        return "0.0%"
    percent = round((makes / attempts) * 100, 1)
    return f"{percent}%"


async def _fetch_player_row(db: AsyncSession, player_id: UUID) -> dict[str, Any]:
    """Load a player row or raise 404."""
    if not await client_db.table_exists(db, PLAYERS_TABLE):
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
        )

    result = await db.execute(
        text(
            """
            SELECT
                id,
                first_name,
                last_name,
                player_code,
                active
            FROM players
            WHERE id = :player_id
            LIMIT 1
            """
        ),
        {"player_id": player_id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
        )
    return dict(row)


async def _aggregate_field_goal_stats(
    db: AsyncSession,
    player_id: UUID,
) -> tuple[int, int]:
    """Return field-goal makes and attempts excluding free-throw drills."""
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return 0, 0

    result = await db.execute(
        text(
            """
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN 0
                            ELSE sd.makes
                        END
                    ),
                    0
                ) AS makes,
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN 0
                            ELSE sd.attempts
                        END
                    ),
                    0
                ) AS attempts
            FROM session_data sd
            LEFT JOIN drills d ON d.id = sd.drill_id
            WHERE sd.player_id = :player_id
            """
        ),
        {
            "player_id": player_id,
            "free_throw_pattern": FREE_THROW_CATEGORY_PATTERN,
        },
    )
    row = result.mappings().first()
    if row is None:
        return 0, 0
    return int(row["makes"]), int(row["attempts"])


async def _load_session_history(
    db: AsyncSession,
    player_id: UUID,
) -> list[dict[str, str]]:
    """Build per-session performance history for a player."""
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return []

    result = await db.execute(
        text(
            """
            SELECT
                ps.id AS session_id,
                COALESCE(
                    NULLIF(TRIM(ps.session_mode), ''),
                    'Training Session'
                ) AS session_mode,
                COALESCE(ps.started_at, ps.created_at, sd.session_date) AS session_when,
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN 0
                            ELSE sd.makes
                        END
                    ),
                    0
                ) AS makes,
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN 0
                            ELSE sd.attempts
                        END
                    ),
                    0
                ) AS attempts
            FROM session_data sd
            JOIN practice_sessions ps ON ps.id = sd.session_id
            LEFT JOIN drills d ON d.id = sd.drill_id
            WHERE sd.player_id = :player_id
            GROUP BY ps.id, ps.session_mode, ps.started_at, ps.created_at, sd.session_date
            ORDER BY session_when DESC NULLS LAST
            LIMIT 20
            """
        ),
        {
            "player_id": player_id,
            "free_throw_pattern": FREE_THROW_CATEGORY_PATTERN,
        },
    )

    history: list[dict[str, str]] = []
    for row in result.mappings().all():
        mapping = dict(row)
        session_mode = str(mapping.get("session_mode") or "Training Session")
        session_name = session_mode.replace("_", " ").title()
        when = mapping.get("session_when")
        if isinstance(when, datetime):
            display_date = _format_display_date(when)
        else:
            display_date = _format_display_date(None)
        makes = int(mapping.get("makes") or 0)
        attempts = int(mapping.get("attempts") or 0)
        history.append(
            {
                "session_name": session_name,
                "date": display_date,
                "performance": _format_performance(makes, attempts),
            }
        )
    return history


async def get_player_statistics(
    db: AsyncSession,
    player_id: UUID,
    *,
    full_name: str | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return aggregate statistics and session history for a player."""
    _ = phone
    player = await _fetch_player_row(db, player_id)
    first = (player.get("first_name") or "").strip()
    last = (player.get("last_name") or "").strip()
    display_name = " ".join(part for part in (first, last) if part).strip() or "Player"
    if full_name and full_name.strip():
        _ = full_name.strip()

    makes, attempts = await _aggregate_field_goal_stats(db, player_id)
    session_history = await _load_session_history(db, player_id)

    logger.info("Loaded statistics for player %s", player_id)
    return {
        "success": True,
        "message": "Player statistics loaded successfully",
        "status": "ready",
        "description": None,
        "link": None,
        "error": None,
        "id": player_id,
        "name": display_name,
        "player_id": player_id,
        "active_field_goals": makes,
        "shooting_percentage": _format_shooting_percentage(makes, attempts),
        "session_history": session_history,
        "full_name": display_name,
        "phone": phone,
    }
