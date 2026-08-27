"""Business logic for Live Practice screen APIs."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import SessionStatus
from app.models.user import User
from app.schemas.live_practice import (
    LivePracticeDrillCreateRequest,
    LivePracticeDrillUpdateRequest,
    LivePracticePlayerStatInput,
    LivePracticeRecordShotsRequest,
    LivePracticeTimerRequest,
)
from app.services import client_db, coach_identity
from app.services.session_summary import compute_shooting_percent

logger = logging.getLogger(__name__)

DRILLS_TABLE = "drills"
PLAYERS_TABLE = "players"
SESSION_DATA_TABLE = "session_data"
LIVE_PRACTICE_CATEGORY = "live_practice"
TIMER_RUNNING = "running"
TIMER_STOPPED = "stopped"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_session_details(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    return {}


async def _column_exists(db: AsyncSession, table_name: str, column_name: str) -> bool:
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


def _ensure_coach_org(user: User) -> UUID:
    if user.org_id is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Coach must belong to an organization to manage live practice",
            status_code=400,
            details=[
                {
                    "field": "org_id",
                    "message": "Coach must belong to an organization to manage live practice",
                }
            ],
        )
    return user.org_id


def _validate_drill_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Drill name is required",
            status_code=400,
            details=[{"field": "drill_name", "message": "Drill name is required"}],
        )
    return cleaned


def _validate_duration(duration: int | None) -> int:
    if duration is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Duration is required",
            status_code=400,
            details=[{"field": "duration", "message": "Duration is required"}],
        )
    if duration < 1:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Duration must be at least 1 second",
            status_code=400,
            details=[{"field": "duration", "message": "Duration must be at least 1 second"}],
        )
    return duration


def _validate_player_stats(
    stats: list[LivePracticePlayerStatInput] | None,
) -> list[dict[str, Any]]:
    if not stats:
        return []

    normalized: list[dict[str, Any]] = []
    details: list[dict[str, str]] = []
    for index, item in enumerate(stats):
        prefix = f"player_stats[{index}]"
        try:
            player_id = UUID(str(item.player_id))
        except ValueError:
            details.append(
                {
                    "field": f"{prefix}.player_id",
                    "message": "Enter a valid player id",
                }
            )
            continue

        if item.shots_made > item.shots_attempted:
            details.append(
                {
                    "field": f"{prefix}.shots_made",
                    "message": "Shots made cannot exceed shots attempted",
                }
            )
        normalized.append(
            {
                "player_id": player_id,
                "shots_made": item.shots_made,
                "shots_attempted": item.shots_attempted,
            }
        )

    if details:
        raise AppException(
            code="VALIDATION_ERROR",
            message="One or more player statistics are invalid",
            status_code=400,
            details=details,
        )
    return normalized


def _validate_shot_counts(*, shots_made: int, shots_attempted: int, player_id: UUID) -> None:
    details: list[dict[str, str]] = []
    if shots_made > shots_attempted:
        details.append(
            {
                "field": "shots_made",
                "message": f"Shots made cannot exceed shots attempted for player {player_id}",
            }
        )
    if details:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Player shot statistics are invalid",
            status_code=400,
            details=details,
        )


def _live_practice_block(details: dict[str, Any]) -> dict[str, Any]:
    block = details.get("live_practice")
    return dict(block) if isinstance(block, dict) else {}


def _timer_block(details: dict[str, Any]) -> dict[str, Any]:
    block = _live_practice_block(details)
    timer = block.get("timer")
    return dict(timer) if isinstance(timer, dict) else {}


def _merge_live_practice_details(
    existing: dict[str, Any],
    *,
    timer: dict[str, Any] | None = None,
    current_drill_id: UUID | None = None,
) -> dict[str, Any]:
    merged = dict(existing)
    live_block = _live_practice_block(merged)
    if timer is not None:
        live_block["timer"] = timer
    if current_drill_id is not None:
        live_block["current_drill_id"] = str(current_drill_id)
    merged["live_practice"] = live_block
    return merged


def _parse_timestamp(value: Any) -> datetime | None:
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
    elapsed = int(timer.get("elapsed_seconds") or 0)
    if timer.get("state") == TIMER_RUNNING:
        started_at = _parse_timestamp(timer.get("started_at"))
        if started_at is not None:
            current = now or _utcnow()
            elapsed += max(0, int((current - started_at).total_seconds()))
    return elapsed


async def _fetch_live_session_row(db: AsyncSession, user_id: UUID) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT id, org_id, session_details, status, started_at
            FROM practice_sessions
            WHERE recorder_user_id = :user_id
              AND session_date = CURRENT_DATE
              AND status = :status
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"user_id": user_id, "status": SessionStatus.IN_PROGRESS.value},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _create_live_session(db: AsyncSession, user: User, org_id: UUID) -> dict[str, Any]:
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)
    recorder = await coach_identity.ensure_recorder_context(db, user)
    session_id = uuid.uuid4()
    now = _utcnow()
    details = _merge_live_practice_details(
        {},
        timer={
            "state": TIMER_STOPPED,
            "elapsed_seconds": 0,
            "duration_seconds": None,
            "started_at": None,
            "stopped_at": None,
        },
    )
    await db.execute(
        text(
            """
            INSERT INTO practice_sessions (
                id, org_id, session_date, session_details, recorder_user_id,
                recorder_coach_id, recorder_type, status, started_at, synced, created_at
            ) VALUES (
                :id, :org_id, CURRENT_DATE, CAST(:session_details AS jsonb),
                :recorder_user_id, :recorder_coach_id, 'coach', :status,
                :started_at, true, :created_at
            )
            """
        ),
        {
            "id": session_id,
            "org_id": org_id,
            "session_details": json.dumps(details),
            "recorder_user_id": user.id,
            "recorder_coach_id": recorder.coach_id,
            "status": SessionStatus.IN_PROGRESS.value,
            "started_at": now,
            "created_at": now,
        },
    )
    await db.commit()
    row = await _fetch_live_session_row(db, user.id)
    if row is None:
        raise AppException(
            code="LIVE_PRACTICE_SESSION_CREATE_FAILED",
            message="Could not create the live practice session",
            status_code=500,
        )
    return row


async def _get_or_create_live_session(db: AsyncSession, user: User) -> dict[str, Any]:
    org_id = _ensure_coach_org(user)
    row = await _fetch_live_session_row(db, user.id)
    if row is not None:
        return row
    return await _create_live_session(db, user, org_id)


async def _persist_session_details(db: AsyncSession, session_id: UUID, details: dict[str, Any]) -> None:
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


async def _drill_name_exists(
    db: AsyncSession,
    name: str,
    *,
    exclude_id: UUID | None = None,
) -> bool:
    params: dict[str, Any] = {"name": name}
    exclude_sql = ""
    if exclude_id is not None:
        exclude_sql = "AND id != :exclude_id"
        params["exclude_id"] = exclude_id
    result = await db.execute(
        text(
            f"""
            SELECT id
            FROM drills
            WHERE LOWER(name) = LOWER(:name)
              {exclude_sql}
            LIMIT 1
            """
        ),
        params,
    )
    return result.scalar_one_or_none() is not None


async def _fetch_drill_row(db: AsyncSession, drill_id: UUID) -> dict[str, Any] | None:
    time_select = "time_seconds" if await _column_exists(db, DRILLS_TABLE, "time_seconds") else "NULL AS time_seconds"
    org_select = (
        "submitted_by_org"
        if await _column_exists(db, DRILLS_TABLE, "submitted_by_org")
        else "NULL AS submitted_by_org"
    )
    result = await db.execute(
        text(
            f"""
            SELECT id, name, category, {time_select}, {org_select}
            FROM drills
            WHERE id = :drill_id
            LIMIT 1
            """
        ),
        {"drill_id": drill_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


def _drill_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": UUID(str(row["id"])),
        "drill_name": str(row["name"]),
        "duration": int(row["time_seconds"] or 0),
        "category": str(row.get("category") or LIVE_PRACTICE_CATEGORY),
    }


def _drill_response(row: dict[str, Any], *, message: str) -> dict[str, Any]:
    item = _drill_item(row)
    return {
        "success": True,
        "message": message,
        "status": "ready",
        "description": "Live practice drill saved",
        "link": None,
        "error": None,
        "address": None,
        **item,
    }


async def _assert_drill_mutable_by_coach(
    db: AsyncSession,
    user: User,
    drill_id: UUID,
) -> dict[str, Any]:
    org_id = _ensure_coach_org(user)
    row = await _fetch_drill_row(db, drill_id)
    if row is None or str(row.get("category")) != LIVE_PRACTICE_CATEGORY:
        raise AppException(
            code="DRILL_NOT_FOUND",
            message="Drill not found",
            status_code=404,
            details=[{"field": "id", "message": "Drill not found"}],
        )
    submitted_org = row.get("submitted_by_org")
    if submitted_org is not None and UUID(str(submitted_org)) != org_id:
        raise AppException(
            code="FORBIDDEN",
            message="You do not have permission to modify this drill",
            status_code=403,
        )
    return row


async def _assert_player_in_org(db: AsyncSession, org_id: UUID, player_id: UUID) -> dict[str, Any]:
    await client_db.require_table(db, PLAYERS_TABLE)
    active_sql = "AND active = true" if await _column_exists(db, PLAYERS_TABLE, "active") else ""
    result = await db.execute(
        text(
            f"""
            SELECT id, first_name, last_name
            FROM players
            WHERE id = :player_id
              AND org_id = :org_id
              {active_sql}
            LIMIT 1
            """
        ),
        {"player_id": player_id, "org_id": org_id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[{"field": "player_id", "message": "Player not found"}],
        )
    return dict(row)


async def create_live_practice_drill(
    db: AsyncSession,
    user: User,
    payload: LivePracticeDrillCreateRequest,
) -> dict[str, Any]:
    """Create a live practice drill for the coach organization."""
    org_id = _ensure_coach_org(user)
    await client_db.require_table(db, DRILLS_TABLE)
    drill_name = _validate_drill_name(payload.drill_name)
    duration = _validate_duration(payload.duration)
    _validate_player_stats(payload.player_stats)

    if await _drill_name_exists(db, drill_name):
        raise AppException(
            code="DRILL_ALREADY_EXISTS",
            message="A drill with this name already exists",
            status_code=409,
            details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
        )

    drill_id = uuid.uuid4()
    columns = ["id", "name", "category"]
    params: dict[str, Any] = {
        "id": drill_id,
        "name": drill_name,
        "category": LIVE_PRACTICE_CATEGORY,
    }
    if await _column_exists(db, DRILLS_TABLE, "time_seconds"):
        columns.append("time_seconds")
        params["time_seconds"] = duration
    if await _column_exists(db, DRILLS_TABLE, "submitted_by_org"):
        columns.append("submitted_by_org")
        params["submitted_by_org"] = org_id
    if await _column_exists(db, DRILLS_TABLE, "approved"):
        columns.append("approved")
        params["approved"] = True

    placeholders = ", ".join(f":{column}" for column in columns)
    column_sql = ", ".join(columns)
    try:
        await db.execute(
            text(f"INSERT INTO drills ({column_sql}) VALUES ({placeholders})"),
            params,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppException(
            code="DRILL_ALREADY_EXISTS",
            message="A drill with this name already exists",
            status_code=409,
            details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
        ) from exc

    row = await _fetch_drill_row(db, drill_id)
    if row is None:
        raise AppException(
            code="DRILL_CREATE_FAILED",
            message="Could not create the drill",
            status_code=500,
        )

    session_row = await _get_or_create_live_session(db, user)
    session_details = _parse_session_details(session_row.get("session_details"))
    updated_details = _merge_live_practice_details(
        session_details,
        current_drill_id=drill_id,
        timer=_timer_block(session_details),
    )
    await _persist_session_details(db, UUID(str(session_row["id"])), updated_details)
    await db.commit()

    logger.info("Created live practice drill %s for org %s", drill_id, org_id)
    return _drill_response(row, message="Drill saved successfully")


async def list_live_practice_drills(db: AsyncSession) -> dict[str, Any]:
    """List live practice drills (public)."""
    await client_db.require_table(db, DRILLS_TABLE)
    time_select = "time_seconds" if await _column_exists(db, DRILLS_TABLE, "time_seconds") else "NULL AS time_seconds"
    result = await db.execute(
        text(
            f"""
            SELECT id, name, category, {time_select}
            FROM drills
            WHERE category = :category
            ORDER BY name ASC
            """
        ),
        {"category": LIVE_PRACTICE_CATEGORY},
    )
    drills = [_drill_item(dict(row)) for row in result.mappings().all()]
    return {
        "success": True,
        "message": "Drills loaded successfully",
        "status": "ready",
        "description": "Live practice drills",
        "link": None,
        "error": None,
        "address": None,
        "drills": drills,
    }


async def update_live_practice_drill(
    db: AsyncSession,
    user: User,
    drill_id: UUID,
    payload: LivePracticeDrillUpdateRequest,
) -> dict[str, Any]:
    """Update a live practice drill owned by the coach organization."""
    row = await _assert_drill_mutable_by_coach(db, user, drill_id)
    _validate_player_stats(payload.player_stats)

    updates: dict[str, Any] = {}
    if payload.drill_name is not None:
        updates["name"] = _validate_drill_name(payload.drill_name)
    if payload.duration is not None:
        if await _column_exists(db, DRILLS_TABLE, "time_seconds"):
            updates["time_seconds"] = _validate_duration(payload.duration)

    if not updates:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one drill field must be provided",
            status_code=400,
            details=[{"field": "body", "message": "At least one drill field must be provided"}],
        )

    if "name" in updates and await _drill_name_exists(
        db,
        str(updates["name"]),
        exclude_id=drill_id,
    ):
        raise AppException(
            code="DRILL_ALREADY_EXISTS",
            message="A drill with this name already exists",
            status_code=409,
            details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
        )

    set_clauses = ", ".join(f"{column} = :{column}" for column in updates)
    try:
        await db.execute(
            text(f"UPDATE drills SET {set_clauses} WHERE id = :drill_id"),
            {"drill_id": drill_id, **updates},
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppException(
            code="DRILL_ALREADY_EXISTS",
            message="A drill with this name already exists",
            status_code=409,
            details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
        ) from exc

    updated = await _fetch_drill_row(db, drill_id)
    if updated is None:
        raise AppException(
            code="DRILL_NOT_FOUND",
            message="Drill not found",
            status_code=404,
        )
    return _drill_response(updated, message="Drill updated successfully")


async def delete_live_practice_drill(
    db: AsyncSession,
    user: User,
    drill_id: UUID,
) -> dict[str, Any]:
    """Delete a live practice drill owned by the coach organization."""
    await _assert_drill_mutable_by_coach(db, user, drill_id)
    await db.execute(text("DELETE FROM drills WHERE id = :drill_id"), {"drill_id": drill_id})
    await db.commit()
    return {
        "success": True,
        "message": "Drill deleted successfully",
        "status": "ready",
        "description": "Live practice drill removed",
        "link": None,
        "error": None,
        "address": None,
        "id": drill_id,
    }


def _timer_response(
    session_row: dict[str, Any],
    timer: dict[str, Any],
    *,
    message: str,
    status: str,
) -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "status": status,
        "description": "Live practice timer",
        "link": None,
        "error": None,
        "address": None,
        "id": UUID(str(session_row["id"])),
        "timer_state": str(timer.get("state") or TIMER_STOPPED),
        "elapsed_seconds": _compute_elapsed_seconds(timer),
        "duration_seconds": timer.get("duration_seconds"),
    }


async def start_live_practice_timer(
    db: AsyncSession,
    user: User,
    payload: LivePracticeTimerRequest,
) -> dict[str, Any]:
    """Start the live practice timer on the coach's active session."""
    session_row = await _get_or_create_live_session(db, user)
    session_id = UUID(str(session_row["id"]))
    details = _parse_session_details(session_row.get("session_details"))
    timer = _timer_block(details)

    if timer.get("state") == TIMER_RUNNING:
        return _timer_response(
            session_row,
            timer,
            message="Timer is already running",
            status=TIMER_RUNNING,
        )

    now = _utcnow()
    if payload.duration is not None:
        timer["duration_seconds"] = _validate_duration(payload.duration)
    timer["state"] = TIMER_RUNNING
    timer["started_at"] = now.isoformat()
    timer["stopped_at"] = None

    updated_details = _merge_live_practice_details(details, timer=timer)
    await _persist_session_details(db, session_id, updated_details)
    await db.commit()
    return _timer_response(
        session_row,
        timer,
        message="Timer started successfully",
        status=TIMER_RUNNING,
    )


async def stop_live_practice_timer(
    db: AsyncSession,
    user: User,
    payload: LivePracticeTimerRequest,
) -> dict[str, Any]:
    """Stop the live practice timer and accumulate elapsed time."""
    _ = payload
    session_row = await _fetch_live_session_row(db, user.id)
    if session_row is None:
        raise AppException(
            code="LIVE_PRACTICE_SESSION_NOT_FOUND",
            message="No active live practice session was found",
            status_code=404,
        )

    session_id = UUID(str(session_row["id"]))
    details = _parse_session_details(session_row.get("session_details"))
    timer = _timer_block(details)
    if timer.get("state") != TIMER_RUNNING:
        return _timer_response(
            session_row,
            timer,
            message="Timer is already stopped",
            status=TIMER_STOPPED,
        )

    now = _utcnow()
    timer["elapsed_seconds"] = _compute_elapsed_seconds(timer, now=now)
    timer["state"] = TIMER_STOPPED
    timer["stopped_at"] = now.isoformat()
    timer["started_at"] = None

    updated_details = _merge_live_practice_details(details, timer=timer)
    await _persist_session_details(db, session_id, updated_details)
    await db.commit()
    return _timer_response(
        session_row,
        timer,
        message="Timer stopped successfully",
        status=TIMER_STOPPED,
    )


async def get_live_practice_timer_status(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return the current live practice timer state."""
    session_row = await _fetch_live_session_row(db, user.id)
    if session_row is None:
        return {
            "success": True,
            "message": "Timer is stopped",
            "status": TIMER_STOPPED,
            "description": "Live practice timer",
            "link": None,
            "error": None,
            "address": None,
            "id": None,
            "timer_state": TIMER_STOPPED,
            "elapsed_seconds": 0,
            "duration_seconds": None,
        }

    timer = _timer_block(_parse_session_details(session_row.get("session_details")))
    return _timer_response(
        session_row,
        timer,
        message="Timer status loaded successfully",
        status=str(timer.get("state") or TIMER_STOPPED),
    )


async def _upsert_session_data(
    db: AsyncSession,
    *,
    session_id: UUID,
    org_id: UUID,
    player_id: UUID,
    drill_id: UUID | None,
    shots_made: int,
    shots_attempted: int,
) -> None:
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return

    if drill_id is None:
        existing = await db.execute(
            text(
                """
                SELECT id
                FROM session_data
                WHERE session_id = :session_id
                  AND player_id = :player_id
                  AND drill_id IS NULL
                LIMIT 1
                """
            ),
            {"session_id": session_id, "player_id": player_id},
        )
    else:
        existing = await db.execute(
            text(
                """
                SELECT id
                FROM session_data
                WHERE session_id = :session_id
                  AND player_id = :player_id
                  AND drill_id = :drill_id
                LIMIT 1
                """
            ),
            {"session_id": session_id, "player_id": player_id, "drill_id": drill_id},
        )
    row = existing.scalar_one_or_none()
    if row is not None:
        await db.execute(
            text(
                """
                UPDATE session_data
                SET makes = :makes,
                    attempts = :attempts,
                    recorded_at = NOW()
                WHERE id = :id
                """
            ),
            {"id": row, "makes": shots_made, "attempts": shots_attempted},
        )
        return

    await db.execute(
        text(
            """
            INSERT INTO session_data (
                id, session_id, org_id, player_id, drill_id, makes, attempts
            ) VALUES (
                :id, :session_id, :org_id, :player_id, :drill_id, :makes, :attempts
            )
            """
        ),
        {
            "id": uuid.uuid4(),
            "session_id": session_id,
            "org_id": org_id,
            "player_id": player_id,
            "drill_id": drill_id,
            "makes": shots_made,
            "attempts": shots_attempted,
        },
    )


async def _fetch_player_statistics(
    db: AsyncSession,
    *,
    session_id: UUID | None,
    player_id: UUID,
) -> tuple[int, int]:
    if session_id is None or not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return 0, 0

    result = await db.execute(
        text(
            """
            SELECT
                COALESCE(SUM(makes), 0) AS shots_made,
                COALESCE(SUM(attempts), 0) AS shots_attempted
            FROM session_data
            WHERE session_id = :session_id
              AND player_id = :player_id
            """
        ),
        {"session_id": session_id, "player_id": player_id},
    )
    row = result.mappings().first()
    if row is None:
        return 0, 0
    return int(row["shots_made"] or 0), int(row["shots_attempted"] or 0)


def _statistics_response(
    *,
    player_id: UUID,
    name: str | None,
    shots_made: int,
    shots_attempted: int,
    message: str,
) -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "status": "ready",
        "description": "Live practice player statistics",
        "link": None,
        "error": None,
        "address": None,
        "id": player_id,
        "player_id": player_id,
        "name": name,
        "shots_made": shots_made,
        "shots_attempted": shots_attempted,
        "shooting_percent": compute_shooting_percent(shots_made, shots_attempted),
    }


async def record_player_shots(
    db: AsyncSession,
    user: User,
    player_id: UUID,
    payload: LivePracticeRecordShotsRequest,
) -> dict[str, Any]:
    """Record shot statistics for a player during live practice."""
    org_id = _ensure_coach_org(user)
    _validate_shot_counts(
        shots_made=payload.shots_made,
        shots_attempted=payload.shots_attempted,
        player_id=player_id,
    )
    player_row = await _assert_player_in_org(db, org_id, player_id)
    session_row = await _get_or_create_live_session(db, user)
    session_id = UUID(str(session_row["id"]))

    if payload.drill_id is not None:
        drill = await _fetch_drill_row(db, payload.drill_id)
        if drill is None:
            raise AppException(
                code="DRILL_NOT_FOUND",
                message="Drill not found",
                status_code=404,
                details=[{"field": "drill_id", "message": "Drill not found"}],
            )

    await _upsert_session_data(
        db,
        session_id=session_id,
        org_id=org_id,
        player_id=player_id,
        drill_id=payload.drill_id,
        shots_made=payload.shots_made,
        shots_attempted=payload.shots_attempted,
    )
    await db.commit()

    name = f"{player_row['first_name']} {player_row['last_name']}".strip()
    return _statistics_response(
        player_id=player_id,
        name=name,
        shots_made=payload.shots_made,
        shots_attempted=payload.shots_attempted,
        message="Player statistics recorded successfully",
    )


async def get_player_statistics(db: AsyncSession, player_id: UUID) -> dict[str, Any]:
    """Retrieve aggregated player statistics for today's active live practice session."""
    await client_db.require_table(db, PLAYERS_TABLE)
    player_result = await db.execute(
        text(
            """
            SELECT id, first_name, last_name, org_id
            FROM players
            WHERE id = :player_id
            LIMIT 1
            """
        ),
        {"player_id": player_id},
    )
    player_row = player_result.mappings().first()
    if player_row is None:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[{"field": "player_id", "message": "Player not found"}],
        )

    session_id: UUID | None = None
    if await client_db.table_exists(db, client_db.PRACTICE_SESSIONS_TABLE):
        session_result = await db.execute(
            text(
                """
                SELECT id
                FROM practice_sessions
                WHERE session_date = CURRENT_DATE
                  AND status = :status
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"status": SessionStatus.IN_PROGRESS.value},
        )
        session_value = session_result.scalar_one_or_none()
        if session_value is not None:
            session_id = UUID(str(session_value))

    shots_made, shots_attempted = await _fetch_player_statistics(
        db,
        session_id=session_id,
        player_id=player_id,
    )
    name = f"{player_row['first_name']} {player_row['last_name']}".strip()
    return _statistics_response(
        player_id=player_id,
        name=name,
        shots_made=shots_made,
        shots_attempted=shots_attempted,
        message="Player statistics loaded successfully",
    )
