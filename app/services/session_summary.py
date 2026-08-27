"""Session summary aggregation and practice lifecycle actions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.enums import SessionStatus
from app.models.user import User
from app.services import client_db

logger = logging.getLogger(__name__)

COMPLETED_STATUS_MESSAGE = "Session Complete! Nice work, coach"
IN_PROGRESS_STATUS_MESSAGE = "Session in progress"
FREE_THROW_CATEGORY_PATTERN = "%free%throw%"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_shooting_percent(makes: int, attempts: int) -> int:
    """Return an integer shooting percentage, or 0 when there are no attempts."""
    if attempts <= 0:
        return 0
    return round((makes / attempts) * 100)


def format_session_time(
    started_at: datetime | None,
    ended_at: datetime | None,
    *,
    now: datetime | None = None,
) -> str:
    """Format elapsed session duration as ``M:SS`` for the mobile status bar."""
    if started_at is None:
        return "0:00"

    end = ended_at or now or _utcnow()
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    elapsed_seconds = max(0, int((end - started_at).total_seconds()))
    minutes, seconds = divmod(elapsed_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _status_message(raw_status: str | None) -> str:
    """Map stored session status to the UI section header string."""
    if raw_status == SessionStatus.COMPLETED.value:
        return COMPLETED_STATUS_MESSAGE
    return IN_PROGRESS_STATUS_MESSAGE


def _summary_link(raw_status: str | None, current_drill_index: int) -> str | None:
    """Suggest the next navigation target for the mobile client."""
    base = settings.FRONTEND_URL.rstrip("/")
    if raw_status == SessionStatus.COMPLETED.value:
        return f"{base}/coach/dashboard"
    if current_drill_index > 0:
        return f"{base}/coach/record/drill"
    return f"{base}/coach/record/next-drill"


async def _fetch_full_session_row(
    db: AsyncSession,
    session_id: UUID,
) -> dict[str, Any] | None:
    """Load extended practice session fields needed for summary and actions."""
    result = await db.execute(
        text(
            """
            SELECT
                id,
                session_mode,
                session_details,
                status,
                created_at,
                started_at,
                ended_at,
                current_drill_index,
                practice_plan_id,
                recorder_user_id
            FROM practice_sessions
            WHERE id = :session_id
            """
        ),
        {"session_id": session_id},
    )
    mapping = result.mappings().first()
    return dict(mapping) if mapping is not None else None


async def _get_owned_session_row(
    db: AsyncSession,
    session_id: UUID,
    user: User,
) -> dict[str, Any]:
    """Return a session row owned by the coach or raise 404/403."""
    row = await _fetch_full_session_row(db, session_id)
    if row is None:
        raise AppException(
            code="SESSION_NOT_FOUND",
            message="Session not found",
            status_code=404,
        )

    owner_id = row.get("recorder_user_id")
    if owner_id is None:
        raise AppException(
            code="SESSION_NOT_FOUND",
            message="Session not found",
            status_code=404,
        )
    if UUID(str(owner_id)) != user.id:
        raise AppException(
            code="SESSION_ACCESS_FORBIDDEN",
            message="You do not have permission to access this session",
            status_code=403,
        )
    return row


async def _load_player_stats(
    db: AsyncSession,
    session_id: UUID,
) -> list[dict[str, Any]]:
    """Aggregate player performance metrics for a session from ``session_data``."""
    if not await client_db.table_exists(db, "session_data"):
        return []

    result = await db.execute(
        text(
            """
            SELECT
                TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, '')) AS player_name,
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
                            THEN sd.attempts
                            ELSE 0
                        END
                    ),
                    0
                ) AS free_throw_attempts,
                COALESCE(
                    SUM(
                        CASE
                            WHEN d.category IS NOT NULL
                                 AND LOWER(d.category) LIKE :free_throw_pattern
                            THEN sd.makes
                            ELSE 0
                        END
                    ),
                    0
                ) AS free_throw_makes
            FROM session_data sd
            JOIN players p ON p.id = sd.player_id
            LEFT JOIN drills d ON d.id = sd.drill_id
            WHERE sd.session_id = :session_id
            GROUP BY p.id, p.first_name, p.last_name
            ORDER BY player_name
            """
        ),
        {
            "session_id": session_id,
            "free_throw_pattern": FREE_THROW_CATEGORY_PATTERN,
        },
    )

    stats: list[dict[str, Any]] = []
    for row in result.mappings().all():
        attempts = int(row["attempts"] or 0)
        makes = int(row["makes"] or 0)
        ft_attempts = int(row["free_throw_attempts"] or 0)
        ft_makes = int(row["free_throw_makes"] or 0)
        stats.append(
            {
                "player_name": str(row["player_name"]).strip(),
                "attempts": attempts,
                "makes": makes,
                "shooting_percent": compute_shooting_percent(makes, attempts),
                "free_throw_attempts": ft_attempts,
                "free_throw_makes": ft_makes,
                "free_throw_percent": compute_shooting_percent(ft_makes, ft_attempts),
            }
        )
    return stats


def _build_summary_payload(
    row: dict[str, Any],
    *,
    player_stats: list[dict[str, Any]],
    message: str,
) -> dict[str, Any]:
    """Shape a session summary dict for the response model."""
    session_id = UUID(str(row["id"]))
    raw_status = row.get("status")
    drill_index = int(row.get("current_drill_index") or 0)
    return {
        "success": True,
        "message": message,
        "status": _status_message(raw_status),
        "description": "Review player performance metrics for this session",
        "link": _summary_link(raw_status, drill_index),
        "error": None,
        "id": session_id,
        "session_id": session_id,
        "player_stats": player_stats,
        "session_time": format_session_time(row.get("started_at"), row.get("ended_at")),
    }


async def get_session_summary(
    db: AsyncSession,
    user: User,
    session_id: UUID,
) -> dict[str, Any]:
    """Return aggregated session summary for the authenticated owning coach."""
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)
    row = await _get_owned_session_row(db, session_id, user)
    player_stats = await _load_player_stats(db, session_id)
    return _build_summary_payload(
        row,
        player_stats=player_stats,
        message="Session summary loaded successfully",
    )


async def advance_next_drill(
    db: AsyncSession,
    user: User,
    session_id: UUID,
) -> dict[str, Any]:
    """Increment the current drill index for an in-progress session."""
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)
    row = await _get_owned_session_row(db, session_id, user)

    if row.get("status") == SessionStatus.COMPLETED.value:
        raise AppException(
            code="SESSION_ALREADY_COMPLETED",
            message="This practice session has already ended",
            status_code=400,
        )

    next_index = int(row.get("current_drill_index") or 0) + 1

    await db.execute(
        text(
            """
            UPDATE practice_sessions
            SET current_drill_index = :next_index,
                status = :status
            WHERE id = :session_id
              AND recorder_user_id = :recorder_user_id
            """
        ),
        {
            "next_index": next_index,
            "status": SessionStatus.IN_PROGRESS.value,
            "session_id": session_id,
            "recorder_user_id": user.id,
        },
    )
    await db.commit()

    updated = await _fetch_full_session_row(db, session_id)
    if updated is None:
        raise AppException(
            code="SESSION_NOT_FOUND",
            message="Session not found",
            status_code=404,
        )

    logger.info("Advanced session %s to drill index %s", session_id, next_index)
    session_uuid = UUID(str(updated["id"]))
    return {
        "success": True,
        "message": "Advanced to the next drill",
        "status": SessionStatus.IN_PROGRESS.value,
        "description": "Continue recording the current practice session",
        "link": _summary_link(updated.get("status"), next_index),
        "error": None,
        "id": session_uuid,
        "session_id": session_uuid,
        "current_drill_index": next_index,
    }


async def end_practice(
    db: AsyncSession,
    user: User,
    session_id: UUID,
) -> dict[str, Any]:
    """Mark a practice session as completed."""
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)
    row = await _get_owned_session_row(db, session_id, user)

    if row.get("status") == SessionStatus.COMPLETED.value:
        raise AppException(
            code="SESSION_ALREADY_COMPLETED",
            message="This practice session has already ended",
            status_code=400,
        )

    now = _utcnow()
    await db.execute(
        text(
            """
            UPDATE practice_sessions
            SET status = :status,
                ended_at = :ended_at
            WHERE id = :session_id
              AND recorder_user_id = :recorder_user_id
            """
        ),
        {
            "status": SessionStatus.COMPLETED.value,
            "ended_at": now,
            "session_id": session_id,
            "recorder_user_id": user.id,
        },
    )
    await db.commit()

    updated = await _fetch_full_session_row(db, session_id)
    if updated is None:
        raise AppException(
            code="SESSION_NOT_FOUND",
            message="Session not found",
            status_code=404,
        )

    player_stats = await _load_player_stats(db, session_id)
    logger.info("Ended practice session %s for coach user %s", session_id, user.id)
    return _build_summary_payload(
        updated,
        player_stats=player_stats,
        message="Practice session ended successfully",
    )
