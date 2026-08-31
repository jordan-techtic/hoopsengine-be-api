"""Business logic for player Active Drill APIs (HE-455, HE-213)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import SessionMode, SessionStatus
from app.models.user import User
from app.schemas.player_drills import (
    PlayerDrillTimerRequest,
    PlayerDrillTimerUpdateRequest,
)
from app.services import client_db, player_identity
from app.services.player_identity import PlayerContext

logger = logging.getLogger(__name__)

DRILLS_TABLE = "drills"
SUBTEAM_DRILL_SETS_TABLE = "subteam_drill_sets"
LIVE_PRACTICE_CATEGORY = "live_practice"
PLAYER_WORKOUT_BLOCK = "player_workout"

TIMER_PLAYING = "playing"
TIMER_STOPPED = "stopped"
TIMER_PAUSED = "paused"
TIMER_RESET = "reset"

TimerStatus = Literal["playing", "paused", "stopped", "reset"]
PlaybackStatus = Literal["playing", "paused", "stopped"]


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


def _timer_block(details: dict[str, Any]) -> dict[str, Any]:
    """Return the timer sub-block from player workout session details."""
    block = _player_workout_block(details)
    timer = block.get("timer")
    return dict(timer) if isinstance(timer, dict) else {}


def _merge_player_workout_details(
    existing: dict[str, Any],
    *,
    timer: dict[str, Any] | None = None,
    drills: list[dict[str, Any]] | None = None,
    current_drill_id: UUID | None = None,
    current_drill_index: int | None = None,
) -> dict[str, Any]:
    """Merge updates into the player_workout session_details block."""
    merged = dict(existing)
    workout_block = _player_workout_block(merged)
    if timer is not None:
        workout_block["timer"] = timer
    if drills is not None:
        workout_block["drills"] = drills
    if current_drill_id is not None:
        workout_block["current_drill_id"] = str(current_drill_id)
    if current_drill_index is not None:
        workout_block["current_drill_index"] = current_drill_index
    merged[PLAYER_WORKOUT_BLOCK] = workout_block
    return merged


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO timestamp from session timer state."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _compute_elapsed_seconds(timer: dict[str, Any], *, now: datetime | None = None) -> int:
    """Return elapsed seconds including active running interval."""
    elapsed = int(timer.get("elapsed_seconds") or 0)
    if timer.get("state") == TIMER_PLAYING:
        started_at = _parse_timestamp(timer.get("started_at"))
        if started_at is not None:
            current = now or _utcnow()
            elapsed += max(0, int((current - started_at).total_seconds()))
    return elapsed


def _format_mm_ss(total_seconds: int) -> str:
    """Format seconds as MM:SS with zero padding."""
    safe_seconds = max(0, int(total_seconds))
    minutes, seconds = divmod(safe_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _format_elapsed(timer: dict[str, Any]) -> str:
    """Format elapsed timer seconds as MM:SS for Active Drill 2."""
    return _format_mm_ss(_compute_elapsed_seconds(timer))


def _parse_timer_mm_ss(value: str) -> int:
    """Parse MM:SS timer input into total elapsed seconds."""
    cleaned = (value or "").strip()
    parts = cleaned.split(":")
    if len(parts) != 2:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Timer must use MM:SS format",
            status_code=400,
            details=[{"field": "timer", "message": "Timer must use MM:SS format"}],
        )
    try:
        minutes = int(parts[0])
        seconds = int(parts[1])
    except ValueError as exc:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Timer must use MM:SS format",
            status_code=400,
            details=[{"field": "timer", "message": "Timer must use MM:SS format"}],
        ) from exc
    if minutes < 0 or seconds < 0 or seconds >= 60:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Timer must use MM:SS format",
            status_code=400,
            details=[{"field": "timer", "message": "Timer must use MM:SS format"}],
        )
    return minutes * 60 + seconds


def _compute_progress(elapsed_seconds: int, duration_seconds: int) -> int:
    """Return drill completion percentage capped between 0 and 100."""
    if duration_seconds <= 0:
        return 0
    percent = round((elapsed_seconds / duration_seconds) * 100)
    return max(0, min(100, percent))


def _playback_status(timer: dict[str, Any]) -> Literal["playing", "paused", "stopped"]:
    """Map internal timer state to Active Drill 2 playback status."""
    state = str(timer.get("state") or TIMER_STOPPED)
    if state == TIMER_PLAYING:
        return TIMER_PLAYING
    if state == TIMER_PAUSED:
        return TIMER_PAUSED
    return TIMER_STOPPED


def _time_remaining(timer: dict[str, Any], *, duration_seconds: int) -> str:
    """Compute countdown time remaining from timer state and drill duration."""
    if duration_seconds <= 0:
        return "00:00"
    elapsed = _compute_elapsed_seconds(timer)
    remaining = max(0, duration_seconds - elapsed)
    return _format_mm_ss(remaining)


def _default_timer(duration_seconds: int) -> dict[str, Any]:
    """Build a stopped timer block for a drill duration."""
    return {
        "state": TIMER_STOPPED,
        "elapsed_seconds": 0,
        "duration_seconds": duration_seconds,
        "started_at": None,
        "stopped_at": None,
    }


def _response_status(timer: dict[str, Any], *, reset: bool = False) -> TimerStatus:
    """Map internal timer state to API status."""
    if reset:
        return TIMER_RESET
    state = str(timer.get("state") or TIMER_STOPPED)
    if state == TIMER_PLAYING:
        return TIMER_PLAYING
    if state == TIMER_PAUSED:
        return TIMER_PAUSED
    return TIMER_STOPPED


def _active_drill_payload(
    *,
    drill_id: UUID,
    name: str,
    timer: dict[str, Any],
    duration_seconds: int,
    message: str,
    description: str | None,
    phone: str | None = None,
    playback_status: Literal["playing", "paused", "stopped"] | None = None,
) -> dict[str, Any]:
    """Build an Active Drill 2 response envelope."""
    elapsed = _compute_elapsed_seconds(timer)
    status = playback_status or _playback_status(timer)
    return {
        "success": True,
        "message": message,
        "description": description,
        "link": None,
        "error": None,
        "id": drill_id,
        "name": name,
        "timer": _format_mm_ss(elapsed),
        "status": status,
        "progress": _compute_progress(elapsed, duration_seconds),
        "phone": phone,
    }


def _detail_description(drill_row: dict[str, Any]) -> str:
    """Return a UI-safe drill description for detail responses."""
    for key in ("description", "directions", "keys"):
        value = drill_row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "Active drill session"


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


async def _persist_session_details(db: AsyncSession, session_id: UUID, details: dict[str, Any]) -> None:
    """Persist JSON session details for a practice session."""
    await db.execute(
        text(
            """
            UPDATE practice_sessions
            SET session_details = CAST(:session_details AS jsonb)
            WHERE id = :session_id
            """
        ),
        {"session_id": session_id, "session_details": json.dumps(details)},
    )


async def _fetch_player_workout_session(db: AsyncSession, user_id: UUID) -> dict[str, Any] | None:
    """Load today's in-progress player workout session for the authenticated user."""
    result = await db.execute(
        text(
            """
            SELECT id, org_id, subteam_id, session_details, status, recorder_player_id
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


async def _fetch_assigned_drills(
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
            SELECT d.id, d.name, d.category, {time_sql}
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


def _serialize_workout_drills(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert assigned drill rows into session_details drill entries."""
    drills: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        drills.append(
            {
                "drill_id": str(row["id"]),
                "name": str(row["name"]),
                "duration_seconds": int(row.get("time_seconds") or 0),
                "sort_order": index,
            }
        )
    return drills


async def _fetch_drill_row(db: AsyncSession, drill_id: UUID) -> dict[str, Any] | None:
    """Load a drill catalog row by id."""
    if not await client_db.table_exists(db, DRILLS_TABLE):
        return None

    time_sql = "COALESCE(time_seconds, 0) AS time_seconds"
    if not await _column_exists(db, DRILLS_TABLE, "time_seconds"):
        time_sql = "0 AS time_seconds"

    description_sql = "description"
    if not await _column_exists(db, DRILLS_TABLE, "description"):
        description_sql = "NULL AS description"

    result = await db.execute(
        text(
            f"""
            SELECT id, name, category, {time_sql}, {description_sql}
            FROM drills
            WHERE id = :drill_id
            LIMIT 1
            """
        ),
        {"drill_id": drill_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _is_drill_assigned(
    db: AsyncSession,
    player_ctx: PlayerContext,
    drill_id: UUID,
) -> bool:
    """Return True when the drill is active on the player's subteam."""
    if player_ctx.subteam_id is None:
        return False
    if not await client_db.table_exists(db, SUBTEAM_DRILL_SETS_TABLE):
        return False

    approved_sql = ""
    if await _column_exists(db, DRILLS_TABLE, "approved"):
        approved_sql = "AND COALESCE(d.approved, true) = true"

    result = await db.execute(
        text(
            f"""
            SELECT sds.id
            FROM subteam_drill_sets sds
            JOIN drills d ON d.id = sds.drill_id
            WHERE sds.subteam_id = :subteam_id
              AND sds.drill_id = :drill_id
              AND COALESCE(sds.active, true) = true
              {approved_sql}
            LIMIT 1
            """
        ),
        {"subteam_id": player_ctx.subteam_id, "drill_id": drill_id},
    )
    return result.scalar_one_or_none() is not None


async def _ensure_player_can_access_drill(
    db: AsyncSession,
    player_ctx: PlayerContext,
    drill_id: UUID,
    *,
    session_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify drill access and return the drill row or raise."""
    drill_row = await _fetch_drill_row(db, drill_id)
    if drill_row is None:
        raise AppException(
            code="DRILL_NOT_FOUND",
            message="Drill not found",
            status_code=404,
            details=[{"field": "drill_id", "message": "Drill not found"}],
        )

    if await _is_drill_assigned(db, player_ctx, drill_id):
        return drill_row

    if session_row is not None:
        details = _parse_session_details(session_row.get("session_details"))
        workout = _player_workout_block(details)
        workout_drills = workout.get("drills") or []
        if any(str(item.get("drill_id")) == str(drill_id) for item in workout_drills):
            return drill_row

    raise AppException(
        code="FORBIDDEN",
        message="You do not have permission to access this drill",
        status_code=403,
        details=[{"field": "drill_id", "message": "You do not have permission to access this drill"}],
    )


async def _create_player_workout_session(
    db: AsyncSession,
    user: User,
    player_ctx: PlayerContext,
    assigned_drills: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create an in-progress player workout session with assigned drills."""
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)
    if not assigned_drills:
        raise AppException(
            code="VALIDATION_ERROR",
            message="No active drills are assigned to your team",
            status_code=400,
            details=[{"field": "drills", "message": "No active drills are assigned to your team"}],
        )

    workout_drills = _serialize_workout_drills(assigned_drills)
    first_drill = assigned_drills[0]
    duration = int(first_drill.get("time_seconds") or 0)
    session_id = uuid.uuid4()
    now = _utcnow()
    details = _merge_player_workout_details(
        {},
        drills=workout_drills,
        current_drill_id=UUID(str(first_drill["id"])),
        current_drill_index=0,
        timer=_default_timer(duration),
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
    row = await _fetch_player_workout_session(db, user.id)
    if row is None:
        raise AppException(
            code="PLAYER_WORKOUT_CREATE_FAILED",
            message="Could not create the player workout session",
            status_code=500,
        )
    return row


async def _get_or_create_player_workout_session(
    db: AsyncSession,
    user: User,
    player_ctx: PlayerContext,
) -> dict[str, Any]:
    """Return today's player workout session, creating one when absent."""
    existing = await _fetch_player_workout_session(db, user.id)
    if existing is not None:
        return existing

    assigned = await _fetch_assigned_drills(db, player_ctx)
    return await _create_player_workout_session(db, user, player_ctx, assigned)


def _current_drill_from_session(
    session_row: dict[str, Any],
    assigned_rows: list[dict[str, Any]],
) -> tuple[UUID, int, dict[str, Any]]:
    """Resolve current drill id, index, and drill row from session state."""
    details = _parse_session_details(session_row.get("session_details"))
    workout = _player_workout_block(details)
    current_id_raw = workout.get("current_drill_id")
    if current_id_raw:
        current_id = UUID(str(current_id_raw))
        for index, row in enumerate(assigned_rows):
            if UUID(str(row["id"])) == current_id:
                return current_id, index, row

    if assigned_rows:
        row = assigned_rows[0]
        return UUID(str(row["id"])), 0, row

    raise AppException(
        code="VALIDATION_ERROR",
        message="No active drills are assigned to your team",
        status_code=400,
        details=[{"field": "drills", "message": "No active drills are assigned to your team"}],
    )


def _timer_payload(
    *,
    drill_id: UUID,
    timer: dict[str, Any],
    duration_seconds: int,
    message: str,
    response_status: TimerStatus,
    phone: str | None = None,
) -> dict[str, Any]:
    """Build a timer action response envelope."""
    return {
        "success": True,
        "message": message,
        "status": response_status,
        "description": "Active drill timer",
        "link": None,
        "error": None,
        "drill_id": drill_id,
        "time_remaining": _time_remaining(timer, duration_seconds=duration_seconds),
        "phone": phone,
    }


async def list_player_drills(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return active drills assigned to the authenticated player."""
    player_ctx = await player_identity.ensure_player_context(db, user)
    assigned_rows = await _fetch_assigned_drills(db, player_ctx)
    session_row = await _fetch_player_workout_session(db, user.id)
    timer = _timer_block(_parse_session_details(session_row.get("session_details"))) if session_row else {}
    current_drill_id = None
    if session_row is not None:
        workout = _player_workout_block(_parse_session_details(session_row.get("session_details")))
        if workout.get("current_drill_id"):
            current_drill_id = UUID(str(workout["current_drill_id"]))

    items: list[dict[str, Any]] = []
    for row in assigned_rows:
        drill_id = UUID(str(row["id"]))
        duration = int(row.get("time_seconds") or 0)
        if current_drill_id == drill_id and session_row is not None:
            item_timer = timer
            item_status = _response_status(timer)
        else:
            item_timer = _default_timer(duration)
            item_status = TIMER_STOPPED
        items.append(
            {
                "drill_id": drill_id,
                "name": str(row["name"]),
                "duration": duration,
                "status": item_status,
                "time_remaining": _time_remaining(item_timer, duration_seconds=duration),
            }
        )

    logger.info("Loaded %s active drills for player %s", len(items), player_ctx.player_id)
    return {
        "success": True,
        "message": "Drills loaded successfully",
        "status": "ready",
        "description": "Active drills assigned to your team",
        "link": None,
        "error": None,
        "phone": phone,
        "drills": items,
    }


async def get_player_drill_detail(
    db: AsyncSession,
    user: User,
    drill_id: UUID,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return drill detail and timer state for one assigned drill."""
    player_ctx = await player_identity.ensure_player_context(db, user)
    session_row = await _fetch_player_workout_session(db, user.id)
    drill_row = await _ensure_player_can_access_drill(
        db,
        player_ctx,
        drill_id,
        session_row=session_row,
    )
    duration = int(drill_row.get("time_seconds") or 0)
    details = _parse_session_details(session_row.get("session_details")) if session_row else {}
    workout = _player_workout_block(details)
    current_id = workout.get("current_drill_id")
    if session_row is not None and current_id and UUID(str(current_id)) == drill_id:
        timer = _timer_block(details)
        response_status = _response_status(timer)
    else:
        timer = _default_timer(duration)
        response_status = TIMER_STOPPED

    elapsed = _compute_elapsed_seconds(timer)
    description = _detail_description(drill_row)

    return {
        "success": True,
        "message": "Drill details loaded successfully",
        "description": description,
        "link": None,
        "error": None,
        "id": drill_id,
        "drill_id": drill_id,
        "name": str(drill_row["name"]),
        "category": str(drill_row.get("category") or "general"),
        "duration": duration,
        "status": response_status,
        "timer": _format_mm_ss(elapsed),
        "progress": _compute_progress(elapsed, duration),
        "time_remaining": _time_remaining(timer, duration_seconds=duration),
        "phone": phone,
    }


async def start_player_drill_timer(
    db: AsyncSession,
    user: User,
    payload: PlayerDrillTimerRequest,
) -> dict[str, Any]:
    """Start the timer for the current or specified player drill."""
    player_ctx = await player_identity.ensure_player_context(db, user)
    assigned_rows = await _fetch_assigned_drills(db, player_ctx)
    session_row = await _get_or_create_player_workout_session(db, user, player_ctx)

    if payload.drill_id is not None:
        await _ensure_player_can_access_drill(
            db,
            player_ctx,
            payload.drill_id,
            session_row=session_row,
        )
        drill_id = payload.drill_id
        drill_row = await _fetch_drill_row(db, drill_id)
        assert drill_row is not None
        drill_index = next(
            (index for index, row in enumerate(assigned_rows) if UUID(str(row["id"])) == drill_id),
            0,
        )
    else:
        drill_id, drill_index, drill_row = _current_drill_from_session(session_row, assigned_rows)

    duration = int(drill_row.get("time_seconds") or 0)
    details = _parse_session_details(session_row.get("session_details"))
    timer = _timer_block(details)

    if timer.get("state") == TIMER_PLAYING and workout_current_matches(details, drill_id):
        return _timer_payload(
            drill_id=drill_id,
            timer=timer,
            duration_seconds=duration,
            message="Timer is already running",
            response_status=TIMER_PLAYING,
            phone=payload.phone,
        )

    now = _utcnow()
    timer = _default_timer(duration)
    timer["state"] = TIMER_PLAYING
    timer["started_at"] = now.isoformat()
    timer["duration_seconds"] = duration

    updated_details = _merge_player_workout_details(
        details,
        timer=timer,
        current_drill_id=drill_id,
        current_drill_index=drill_index,
    )
    await _persist_session_details(db, UUID(str(session_row["id"])), updated_details)
    await db.commit()

    logger.info("Started player drill timer for drill %s", drill_id)
    return _timer_payload(
        drill_id=drill_id,
        timer=timer,
        duration_seconds=duration,
        message="Timer started successfully",
        response_status=TIMER_PLAYING,
        phone=payload.phone,
    )


def workout_current_matches(details: dict[str, Any], drill_id: UUID) -> bool:
    """Return True when the session's current drill matches the provided id."""
    workout = _player_workout_block(details)
    current_id = workout.get("current_drill_id")
    return current_id is not None and UUID(str(current_id)) == drill_id


async def reset_player_drill_timer(
    db: AsyncSession,
    user: User,
    payload: PlayerDrillTimerRequest,
) -> dict[str, Any]:
    """Reset the current player drill timer to its initial duration."""
    player_ctx = await player_identity.ensure_player_context(db, user)
    assigned_rows = await _fetch_assigned_drills(db, player_ctx)
    session_row = await _fetch_player_workout_session(db, user.id)
    if session_row is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Start a workout before resetting the drill timer",
            status_code=400,
            details=[
                {
                    "field": "workout",
                    "message": "Start a workout before resetting the drill timer",
                }
            ],
        )

    if payload.drill_id is not None:
        await _ensure_player_can_access_drill(
            db,
            player_ctx,
            payload.drill_id,
            session_row=session_row,
        )
        drill_id = payload.drill_id
        drill_row = await _fetch_drill_row(db, drill_id)
        assert drill_row is not None
    else:
        drill_id, _, drill_row = _current_drill_from_session(session_row, assigned_rows)

    duration = int(drill_row.get("time_seconds") or 0)
    details = _parse_session_details(session_row.get("session_details"))
    timer = _default_timer(duration)

    updated_details = _merge_player_workout_details(
        details,
        timer=timer,
        current_drill_id=drill_id,
    )
    await _persist_session_details(db, UUID(str(session_row["id"])), updated_details)
    await db.commit()

    logger.info("Reset player drill timer for drill %s", drill_id)
    return _timer_payload(
        drill_id=drill_id,
        timer=timer,
        duration_seconds=duration,
        message="Timer reset successfully",
        response_status=TIMER_RESET,
        phone=payload.phone,
    )


async def stop_player_drill_timer(
    db: AsyncSession,
    user: User,
    drill_id: UUID,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Stop the timer for the specified player drill."""
    player_ctx = await player_identity.ensure_player_context(db, user)
    session_row = await _fetch_player_workout_session(db, user.id)
    if session_row is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Start a workout before stopping the drill timer",
            status_code=400,
            details=[
                {
                    "field": "workout",
                    "message": "Start a workout before stopping the drill timer",
                }
            ],
        )

    drill_row = await _ensure_player_can_access_drill(
        db,
        player_ctx,
        drill_id,
        session_row=session_row,
    )
    duration = int(drill_row.get("time_seconds") or 0)
    details = _parse_session_details(session_row.get("session_details"))
    timer = _timer_block(details)

    if not workout_current_matches(details, drill_id):
        raise AppException(
            code="VALIDATION_ERROR",
            message="This drill is not the active drill session",
            status_code=400,
            details=[
                {
                    "field": "drill_id",
                    "message": "This drill is not the active drill session",
                }
            ],
        )

    now = _utcnow()
    if timer.get("state") == TIMER_PLAYING:
        timer["elapsed_seconds"] = _compute_elapsed_seconds(timer, now=now)
    timer["state"] = TIMER_STOPPED
    timer["stopped_at"] = now.isoformat()
    timer["started_at"] = None
    timer["duration_seconds"] = duration

    updated_details = _merge_player_workout_details(details, timer=timer, current_drill_id=drill_id)
    await _persist_session_details(db, UUID(str(session_row["id"])), updated_details)
    await db.commit()

    logger.info("Stopped player drill timer for drill %s", drill_id)
    return _timer_payload(
        drill_id=drill_id,
        timer=timer,
        duration_seconds=duration,
        message="Timer stopped successfully",
        response_status=TIMER_STOPPED,
        phone=phone,
    )


async def play_player_drill(
    db: AsyncSession,
    user: User,
    drill_id: UUID,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Start drill playback for Active Drill 2 (HE-213)."""
    player_ctx = await player_identity.ensure_player_context(db, user)
    assigned_rows = await _fetch_assigned_drills(db, player_ctx)
    session_row = await _get_or_create_player_workout_session(db, user, player_ctx)
    drill_row = await _ensure_player_can_access_drill(
        db,
        player_ctx,
        drill_id,
        session_row=session_row,
    )

    drill_index = next(
        (index for index, row in enumerate(assigned_rows) if UUID(str(row["id"])) == drill_id),
        0,
    )
    duration = int(drill_row.get("time_seconds") or 0)
    details = _parse_session_details(session_row.get("session_details"))
    timer = _timer_block(details)

    if timer.get("state") != TIMER_PLAYING or not workout_current_matches(details, drill_id):
        now = _utcnow()
        timer = _default_timer(duration)
        timer["state"] = TIMER_PLAYING
        timer["started_at"] = now.isoformat()
        timer["duration_seconds"] = duration

        updated_details = _merge_player_workout_details(
            details,
            timer=timer,
            current_drill_id=drill_id,
            current_drill_index=drill_index,
        )
        await _persist_session_details(db, UUID(str(session_row["id"])), updated_details)
        await db.commit()
        message = "Drill playback started successfully"
    else:
        message = "Drill playback is already running"

    logger.info("Started player drill playback for drill %s", drill_id)
    return _active_drill_payload(
        drill_id=drill_id,
        name=str(drill_row["name"]),
        timer=timer,
        duration_seconds=duration,
        message=message,
        description=_detail_description(drill_row),
        phone=phone,
        playback_status=TIMER_PLAYING,
    )


async def update_player_drill_timer(
    db: AsyncSession,
    user: User,
    drill_id: UUID,
    payload: PlayerDrillTimerUpdateRequest,
) -> dict[str, Any]:
    """Update elapsed timer and playback status for Active Drill 2 (HE-213)."""
    player_ctx = await player_identity.ensure_player_context(db, user)
    session_row = await _fetch_player_workout_session(db, user.id)
    if session_row is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Start drill playback before updating the timer",
            status_code=400,
            details=[
                {
                    "field": "workout",
                    "message": "Start drill playback before updating the timer",
                }
            ],
        )

    drill_row = await _ensure_player_can_access_drill(
        db,
        player_ctx,
        drill_id,
        session_row=session_row,
    )
    duration = int(drill_row.get("time_seconds") or 0)
    details = _parse_session_details(session_row.get("session_details"))

    if not workout_current_matches(details, drill_id):
        raise AppException(
            code="VALIDATION_ERROR",
            message="This drill is not the active drill session",
            status_code=400,
            details=[
                {
                    "field": "drill_id",
                    "message": "This drill is not the active drill session",
                }
            ],
        )

    elapsed_seconds = _parse_timer_mm_ss(payload.timer)
    if duration > 0 and elapsed_seconds > duration:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Timer cannot exceed the drill duration",
            status_code=400,
            details=[
                {
                    "field": "timer",
                    "message": "Timer cannot exceed the drill duration",
                }
            ],
        )

    timer = _timer_block(details)
    timer["elapsed_seconds"] = elapsed_seconds
    timer["duration_seconds"] = duration
    timer["started_at"] = None
    timer["stopped_at"] = None

    target_status = payload.status or _playback_status(timer)
    if target_status == TIMER_PLAYING:
        timer["state"] = TIMER_PLAYING
        timer["started_at"] = _utcnow().isoformat()
    elif target_status == TIMER_PAUSED:
        timer["state"] = TIMER_PAUSED
    else:
        timer["state"] = TIMER_STOPPED
        timer["stopped_at"] = _utcnow().isoformat()

    updated_details = _merge_player_workout_details(details, timer=timer, current_drill_id=drill_id)
    await _persist_session_details(db, UUID(str(session_row["id"])), updated_details)
    await db.commit()

    logger.info("Updated player drill timer for drill %s", drill_id)
    return _active_drill_payload(
        drill_id=drill_id,
        name=str(drill_row["name"]),
        timer=timer,
        duration_seconds=duration,
        message="Timer updated successfully",
        description=_detail_description(drill_row),
        phone=payload.phone,
        playback_status=target_status,
    )
