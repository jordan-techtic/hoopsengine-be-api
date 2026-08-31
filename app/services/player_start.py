"""Business logic for player Start screen workout APIs (HE-229)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import SessionMode, SessionStatus
from app.models.user import User
from app.schemas.player_start import PlayerStartDrillItem, PlayerStartWorkoutRequest
from app.services import client_db, player_identity
from app.services.player_identity import PlayerContext
from app.services.player_statistics import _aggregate_field_goal_stats, _format_shooting_percentage
from app.services.session_summary import FREE_THROW_CATEGORY_PATTERN

logger = logging.getLogger(__name__)

DRILLS_TABLE = "drills"
SUBTEAM_DRILL_SETS_TABLE = "subteam_drill_sets"
PLAYER_WORKOUT_BLOCK = "player_workout"
LIVE_PRACTICE_CATEGORY = "live_practice"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_session_details(raw: Any) -> dict[str, Any]:
    """Parse session_details JSONB into a dictionary."""
    if raw is None:
        return {}
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    return {}


def _player_workout_block(details: dict[str, Any]) -> dict[str, Any]:
    """Return the player_workout block from session details."""
    block = details.get(PLAYER_WORKOUT_BLOCK)
    return dict(block) if isinstance(block, dict) else {}


def _seconds_to_minutes(seconds: int) -> int:
    """Convert stored seconds to whole minutes for the Start screen."""
    if seconds <= 0:
        return 1
    return max(1, round(seconds / 60))


def _minutes_to_seconds(minutes: int) -> int:
    """Convert UI minutes to stored seconds."""
    return max(60, int(minutes) * 60)


def _drill_item_from_row(row: dict[str, Any]) -> PlayerStartDrillItem:
    """Build a Start screen drill item from a catalog row."""
    seconds = int(row.get("time_seconds") or 0)
    return PlayerStartDrillItem(
        name=str(row["name"]),
        duration=_seconds_to_minutes(seconds),
    )


def _drill_item_from_session_entry(entry: dict[str, Any]) -> PlayerStartDrillItem | None:
    """Build a Start screen drill item from session_details storage."""
    name = str(entry.get("name") or "").strip()
    if not name:
        return None
    if entry.get("duration_seconds") is not None:
        duration = _seconds_to_minutes(int(entry["duration_seconds"]))
    elif entry.get("duration") is not None:
        duration = max(1, int(entry["duration"]))
    else:
        duration = 1
    return PlayerStartDrillItem(name=name, duration=duration)


def _serialize_workout_drills(items: list[PlayerStartDrillItem]) -> list[dict[str, Any]]:
    """Convert request drill items into session_details storage."""
    serialized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        serialized.append(
            {
                "name": item.name,
                "duration": item.duration,
                "duration_seconds": _minutes_to_seconds(item.duration),
                "sort_order": index,
            }
        )
    return serialized


def _default_timer(duration_seconds: int) -> dict[str, Any]:
    """Build a stopped timer block for a workout drill."""
    return {
        "state": "stopped",
        "elapsed_seconds": 0,
        "duration_seconds": duration_seconds,
        "started_at": None,
        "stopped_at": None,
    }


def _merge_player_workout_details(
    existing: dict[str, Any],
    *,
    timer: dict[str, Any] | None = None,
    drills: list[dict[str, Any]] | None = None,
    current_drill_index: int | None = None,
) -> dict[str, Any]:
    """Merge updates into the player_workout session_details block."""
    merged = dict(existing)
    workout_block = _player_workout_block(merged)
    if timer is not None:
        workout_block["timer"] = timer
    if drills is not None:
        workout_block["drills"] = drills
    if current_drill_index is not None:
        workout_block["current_drill_index"] = current_drill_index
    merged[PLAYER_WORKOUT_BLOCK] = workout_block
    return merged


async def _column_exists(db: AsyncSession, table_name: str, column_name: str) -> bool:
    """Return True when a column exists on a public table."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
            )
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(exists)


async def _fetch_assigned_drill_rows(
    db: AsyncSession,
    player_ctx: PlayerContext,
) -> list[dict[str, Any]]:
    """Return active drills assigned to the player's subteam."""
    if player_ctx.subteam_id is None:
        return []
    if not await client_db.table_exists(db, SUBTEAM_DRILL_SETS_TABLE):
        return []
    if not await client_db.table_exists(db, DRILLS_TABLE):
        return []

    approved_sql = ""
    if await _column_exists(db, DRILLS_TABLE, "approved"):
        approved_sql = "AND COALESCE(d.approved, true) = true"

    time_sql = "COALESCE(d.time_seconds, 0) AS time_seconds"
    if not await _column_exists(db, DRILLS_TABLE, "time_seconds"):
        time_sql = "0 AS time_seconds"

    result = await db.execute(
        text(
            f"""
            SELECT d.id, d.name, {time_sql}
            FROM subteam_drill_sets sds
            JOIN drills d ON d.id = sds.drill_id
            WHERE sds.subteam_id = :subteam_id
              AND COALESCE(sds.active, true) = true
              AND d.category != :live_practice_category
              {approved_sql}
            ORDER BY sds.sort_order ASC, d.name ASC
            """
        ),
        {
            "subteam_id": player_ctx.subteam_id,
            "live_practice_category": LIVE_PRACTICE_CATEGORY,
        },
    )
    return [dict(row) for row in result.mappings().all()]


async def _fetch_in_progress_workout(
    db: AsyncSession,
    user_id: UUID,
) -> dict[str, Any] | None:
    """Load today's in-progress player workout session."""
    if not await client_db.table_exists(db, client_db.PRACTICE_SESSIONS_TABLE):
        return None

    has_recorder_user = await _column_exists(db, client_db.PRACTICE_SESSIONS_TABLE, "recorder_user_id")
    has_session_mode = await _column_exists(db, client_db.PRACTICE_SESSIONS_TABLE, "session_mode")
    if not has_recorder_user or not has_session_mode:
        return None

    result = await db.execute(
        text(
            """
            SELECT id, session_details
            FROM practice_sessions
            WHERE recorder_user_id = :user_id
              AND session_date = CURRENT_DATE
              AND session_mode = :session_mode
              AND status = :status
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {
            "user_id": user_id,
            "session_mode": SessionMode.PLAYER_WORKOUT.value,
            "status": SessionStatus.IN_PROGRESS.value,
        },
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


def _drills_from_session_row(session_row: dict[str, Any]) -> list[PlayerStartDrillItem]:
    """Extract today's drill list from an in-progress workout session."""
    details = _parse_session_details(session_row.get("session_details"))
    workout = _player_workout_block(details)
    items: list[PlayerStartDrillItem] = []
    for entry in workout.get("drills") or []:
        if not isinstance(entry, dict):
            continue
        item = _drill_item_from_session_entry(entry)
        if item is not None:
            items.append(item)
    return items


async def _count_player_sessions(db: AsyncSession, player_id: UUID) -> int:
    """Count distinct practice sessions recorded for a player."""
    if not await client_db.table_exists(db, "session_data"):
        return 0

    result = await db.scalar(
        text(
            """
            SELECT COUNT(DISTINCT session_id)
            FROM session_data
            WHERE player_id = :player_id
            """
        ),
        {"player_id": player_id},
    )
    return int(result or 0)


async def _count_player_attempts(db: AsyncSession, player_id: UUID) -> int:
    """Count total shot attempts for a player excluding free throws."""
    if not await client_db.table_exists(db, "session_data"):
        return 0

    result = await db.scalar(
        text(
            """
            SELECT COALESCE(
                SUM(
                    CASE
                        WHEN d.category IS NOT NULL
                             AND LOWER(d.category) LIKE :free_throw_pattern
                        THEN 0
                        ELSE sd.attempts
                    END
                ),
                0
            )
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
    return int(result or 0)


async def _build_statistics(
    db: AsyncSession,
    player_ctx: PlayerContext,
    drills: list[PlayerStartDrillItem],
) -> dict[str, Any]:
    """Aggregate quick stats for the Start screen."""
    makes, attempts = await _aggregate_field_goal_stats(db, player_ctx.player_id)
    total_sessions = await _count_player_sessions(db, player_ctx.player_id)
    total_attempts = await _count_player_attempts(db, player_ctx.player_id)
    return {
        "total_sessions": total_sessions,
        "total_attempts": total_attempts,
        "shooting_percentage": _format_shooting_percentage(makes, attempts),
        "drill_count": len(drills),
        "total_duration_minutes": sum(item.duration for item in drills),
    }


async def _resolve_today_drills(
    db: AsyncSession,
    player_ctx: PlayerContext,
    session_row: dict[str, Any] | None,
) -> list[PlayerStartDrillItem]:
    """Load today's drill list from assignments or the active workout session."""
    assigned_rows = await _fetch_assigned_drill_rows(db, player_ctx)
    if assigned_rows:
        return [_drill_item_from_row(row) for row in assigned_rows]

    if session_row is not None:
        session_drills = _drills_from_session_row(session_row)
        if session_drills:
            return session_drills

    return []


def _validate_workout_drills(drills: list[PlayerStartDrillItem]) -> None:
    """Validate workout drill payload and raise 400 on business rule failures."""
    if not drills:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one drill is required to start a workout",
            status_code=400,
            details=[{"field": "drills", "message": "At least one drill is required to start a workout"}],
        )

    for index, drill in enumerate(drills):
        if not drill.name.strip():
            raise AppException(
                code="VALIDATION_ERROR",
                message="Drill name is required",
                status_code=400,
                details=[
                    {
                        "field": f"drills[{index}].name",
                        "message": "Drill name is required",
                    }
                ],
            )
        if drill.duration < 1:
            raise AppException(
                code="VALIDATION_ERROR",
                message="Drill duration must be at least 1 minute",
                status_code=400,
                details=[
                    {
                        "field": f"drills[{index}].duration",
                        "message": "Drill duration must be at least 1 minute",
                    }
                ],
            )


async def get_player_start(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return workout statistics and today's drill list for the Start screen."""
    player_ctx = await player_identity.ensure_player_context(db, user)
    session_row = await _fetch_in_progress_workout(db, user.id)
    drills = await _resolve_today_drills(db, player_ctx, session_row)
    statistics = await _build_statistics(db, player_ctx, drills)

    workout_id = UUID(str(session_row["id"])) if session_row is not None else None
    description = (
        "Ready to train? Review today's drills and quick stats before starting."
        if drills
        else "No drills are assigned for today. Contact your coach to add drills."
    )

    logger.info("Loaded player start data for user %s", user.id)
    return {
        "success": True,
        "message": "Workout start data loaded successfully",
        "status": "ready",
        "description": description,
        "link": None,
        "error": None,
        "workout_id": workout_id,
        "phone": phone,
        "statistics": statistics,
        "drills": [item.model_dump() for item in drills],
    }


async def start_player_workout(
    db: AsyncSession,
    user: User,
    payload: PlayerStartWorkoutRequest,
) -> dict[str, Any]:
    """Create an in-progress player workout session from the submitted drill list."""
    player_ctx = await player_identity.ensure_player_context(db, user)
    drills = payload.drills or []
    _validate_workout_drills(drills)

    existing = await _fetch_in_progress_workout(db, user.id)
    if existing is not None:
        raise AppException(
            code="WORKOUT_ALREADY_ACTIVE",
            message="A workout is already in progress for today",
            status_code=409,
            details=[
                {
                    "field": "workout",
                    "message": "A workout is already in progress for today",
                }
            ],
        )

    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)
    serialized_drills = _serialize_workout_drills(drills)
    first_duration = serialized_drills[0]["duration_seconds"]
    session_id = uuid.uuid4()
    now = _utcnow()
    details = _merge_player_workout_details(
        {},
        timer=_default_timer(first_duration),
        drills=serialized_drills,
        current_drill_index=0,
    )

    has_recorder_player = await _column_exists(db, client_db.PRACTICE_SESSIONS_TABLE, "recorder_player_id")
    has_recorder_user = await _column_exists(db, client_db.PRACTICE_SESSIONS_TABLE, "recorder_user_id")
    has_session_mode = await _column_exists(db, client_db.PRACTICE_SESSIONS_TABLE, "session_mode")

    recorder_player_sql = ", recorder_player_id" if has_recorder_player else ""
    recorder_player_val = ", :recorder_player_id" if has_recorder_player else ""
    recorder_user_sql = ", recorder_user_id" if has_recorder_user else ""
    recorder_user_val = ", :recorder_user_id" if has_recorder_user else ""
    session_mode_sql = ", session_mode" if has_session_mode else ""
    session_mode_val = ", :session_mode" if has_session_mode else ""

    params: dict[str, Any] = {
        "id": session_id,
        "org_id": player_ctx.org_id,
        "subteam_id": player_ctx.subteam_id,
        "session_details": json.dumps(details),
        "status": SessionStatus.IN_PROGRESS.value,
        "started_at": now,
        "created_at": now,
    }
    if has_recorder_player:
        params["recorder_player_id"] = player_ctx.player_id
    if has_recorder_user:
        params["recorder_user_id"] = user.id
    if has_session_mode:
        params["session_mode"] = SessionMode.PLAYER_WORKOUT.value

    await db.execute(
        text(
            f"""
            INSERT INTO practice_sessions (
                id, org_id, subteam_id, session_date, session_details,
                recorder_type, status, started_at, synced, created_at
                {recorder_player_sql}{recorder_user_sql}{session_mode_sql}
            ) VALUES (
                :id, :org_id, :subteam_id, CURRENT_DATE, CAST(:session_details AS jsonb),
                'player', :status, :started_at, true, :created_at
                {recorder_player_val}{recorder_user_val}{session_mode_val}
            )
            """
        ),
        params,
    )
    await db.commit()

    logger.info("Started player workout session %s for user %s", session_id, user.id)
    return {
        "success": True,
        "message": "Workout started successfully",
        "status": "started",
        "description": "Your workout session is ready",
        "link": None,
        "error": None,
        "workout_id": session_id,
        "phone": payload.phone,
        "drills": [item.model_dump() for item in drills],
    }
