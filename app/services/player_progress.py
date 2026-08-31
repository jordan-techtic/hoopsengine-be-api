"""Business logic for authenticated player My Progress APIs."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import client_db, player_identity
from app.services.session_summary import FREE_THROW_CATEGORY_PATTERN

logger = logging.getLogger(__name__)

SESSION_DATA_TABLE = "session_data"
PRACTICE_SESSIONS_TABLE = "practice_sessions"
DRILLS_TABLE = "drills"


def _player_display_name(row: dict[str, Any]) -> str:
    """Return a display name from a players row."""
    first = (row.get("first_name") or "").strip()
    last = (row.get("last_name") or "").strip()
    return " ".join(part for part in (first, last) if part).strip() or "Player"


def format_progress_shooting_percentage(makes: int, attempts: int) -> str:
    """Format aggregate shooting percentage as an integer percent string."""
    if attempts <= 0:
        return "0%"
    percent = round((makes / attempts) * 100)
    return f"{percent}%"


def format_iso_date(value: datetime | None) -> str:
    """Format a session timestamp as ISO YYYY-MM-DD."""
    if value is None:
        return "1970-01-01"
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.date().isoformat()


def _base_envelope(
    *,
    player_id: UUID,
    name: str,
    message: str,
    status: str,
    description: str | None,
    phone: str | None,
) -> dict[str, Any]:
    """Build shared mobile envelope fields for progress responses."""
    return {
        "success": True,
        "message": message,
        "status": status,
        "description": description,
        "link": None,
        "error": None,
        "id": player_id,
        "name": name,
        "phone": phone,
    }


async def _aggregate_field_goal_stats(
    db: AsyncSession,
    player_id: UUID,
) -> tuple[int, int, int]:
    """Return makes, attempts, and completed session count excluding free throws."""
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return 0, 0, 0

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
                ) AS attempts,
                COUNT(DISTINCT sd.session_id) AS completed_sessions
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
        return 0, 0, 0
    return int(row["makes"]), int(row["attempts"]), int(row["completed_sessions"])


async def _load_progress_session_history(
    db: AsyncSession,
    player_id: UUID,
) -> list[dict[str, Any]]:
    """Build per-session drill history rows for the My Progress screen."""
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return []

    joins_practice_sessions = await client_db.table_exists(db, PRACTICE_SESSIONS_TABLE)
    if joins_practice_sessions:
        query = """
            SELECT
                COALESCE(
                    NULLIF(TRIM(d.name), ''),
                    NULLIF(TRIM(ps.session_mode), ''),
                    'Training Session'
                ) AS drill,
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
            GROUP BY ps.id, drill, ps.started_at, ps.created_at, sd.session_date
            ORDER BY session_when DESC NULLS LAST
            LIMIT 50
        """
    else:
        query = """
            SELECT
                COALESCE(NULLIF(TRIM(d.name), ''), 'Training Session') AS drill,
                sd.session_date AS session_when,
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
            GROUP BY sd.session_id, drill, sd.session_date
            ORDER BY session_when DESC NULLS LAST
            LIMIT 50
        """

    result = await db.execute(
        text(query),
        {
            "player_id": player_id,
            "free_throw_pattern": FREE_THROW_CATEGORY_PATTERN,
        },
    )

    history: list[dict[str, Any]] = []
    for row in result.mappings().all():
        mapping = dict(row)
        when = mapping.get("session_when")
        session_when = when if isinstance(when, datetime) else None
        history.append(
            {
                "date": format_iso_date(session_when),
                "drill": str(mapping.get("drill") or "Training Session"),
                "attempts": int(mapping.get("attempts") or 0),
                "makes": int(mapping.get("makes") or 0),
            }
        )
    return history


async def _load_drill_performance(
    db: AsyncSession,
    player_id: UUID,
) -> list[dict[str, Any]]:
    """Aggregate field-goal performance grouped by drill name."""
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return []

    result = await db.execute(
        text(
            """
            SELECT
                COALESCE(NULLIF(TRIM(d.name), ''), 'Training Session') AS drill,
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
            GROUP BY drill
            ORDER BY attempts DESC, drill ASC
            """
        ),
        {
            "player_id": player_id,
            "free_throw_pattern": FREE_THROW_CATEGORY_PATTERN,
        },
    )

    items: list[dict[str, Any]] = []
    for row in result.mappings().all():
        mapping = dict(row)
        makes = int(mapping.get("makes") or 0)
        attempts = int(mapping.get("attempts") or 0)
        items.append(
            {
                "drill": str(mapping.get("drill") or "Training Session"),
                "attempts": attempts,
                "makes": makes,
                "shooting_percentage": format_progress_shooting_percentage(makes, attempts),
            }
        )
    return items


async def get_my_progress(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return aggregate progress metrics for the authenticated player."""
    context = await player_identity.ensure_player_context(db, user)
    name = _player_display_name(context.row)
    makes, attempts, completed_sessions = await _aggregate_field_goal_stats(
        db,
        context.player_id,
    )

    status = "ready" if completed_sessions > 0 else "empty"
    description = None if status == "ready" else "No sessions have been logged yet"

    logger.info("Loaded my progress for player %s", context.player_id)
    return {
        **_base_envelope(
            player_id=context.player_id,
            name=name,
            message="Player progress loaded successfully",
            status=status,
            description=description,
            phone=phone,
        ),
        "completed_sessions": completed_sessions,
        "total_attempts": attempts,
        "makes": makes,
        "shooting_percentage": format_progress_shooting_percentage(makes, attempts),
    }


async def get_session_history(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return drill session history rows for the authenticated player."""
    context = await player_identity.ensure_player_context(db, user)
    name = _player_display_name(context.row)
    session_history = await _load_progress_session_history(db, context.player_id)

    status = "ready" if session_history else "empty"
    description = None if status == "ready" else "No session history is available yet"

    logger.info("Loaded session history for player %s", context.player_id)
    return {
        **_base_envelope(
            player_id=context.player_id,
            name=name,
            message="Session history loaded successfully",
            status=status,
            description=description,
            phone=phone,
        ),
        "session_history": session_history,
    }


async def get_drill_performance(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return per-drill performance metrics for the authenticated player."""
    context = await player_identity.ensure_player_context(db, user)
    name = _player_display_name(context.row)
    drill_performance = await _load_drill_performance(db, context.player_id)

    status = "ready" if drill_performance else "empty"
    description = None if status == "ready" else "No drill performance data is available yet"

    logger.info("Loaded drill performance for player %s", context.player_id)
    return {
        **_base_envelope(
            player_id=context.player_id,
            name=name,
            message="Drill performance loaded successfully",
            status=status,
            description=description,
            phone=phone,
        ),
        "drill_performance": drill_performance,
    }
