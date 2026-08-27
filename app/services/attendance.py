"""Business logic for coach Attendance screen APIs."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.enums import SessionStatus
from app.models.user import User
from app.schemas.attendance import AttendanceStartPracticeRequest
from app.services import client_db, coach_identity

logger = logging.getLogger(__name__)

PLAYERS_TABLE = "players"
ATTENDANCE_STATUS_PRESENT = "present"
ATTENDANCE_STATUS_ABSENT = "absent"
ATTENDANCE_DESCRIPTION = "Only present players will appear in recording"


def resolve_attendance_search_text(
    *,
    search_query: str | None,
    full_name: str | None,
) -> str:
    """Return normalized search text or raise 400 when both inputs are empty."""
    candidate = (search_query or full_name or "").strip()
    if not candidate:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Search query is required",
            status_code=400,
            details=[
                {
                    "field": "full_name",
                    "message": "Provide full_name or search_query to search players",
                }
            ],
        )
    return candidate


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_session_details(raw: Any) -> dict[str, Any]:
    """Normalize session_details from DB into a dict."""
    if raw is None:
        return {}
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    return {}


def _attendance_map(details: dict[str, Any]) -> dict[str, str]:
    """Extract the player attendance map from session_details."""
    attendance = details.get("attendance")
    if not isinstance(attendance, dict):
        return {}
    players = attendance.get("players")
    if not isinstance(players, dict):
        return {}
    return {str(key): str(value) for key, value in players.items()}


def _build_attendance_details(existing: dict[str, Any], players_map: dict[str, str]) -> dict[str, Any]:
    """Merge attendance player statuses into session_details."""
    merged = dict(existing)
    attendance = dict(merged.get("attendance") or {})
    attendance["players"] = players_map
    merged["attendance"] = attendance
    return merged


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


async def _fetch_active_players(db: AsyncSession, org_id: UUID) -> list[dict[str, Any]]:
    """Load all active players for the organization."""
    await client_db.require_table(db, PLAYERS_TABLE)

    jersey_column = await _column_exists(db, PLAYERS_TABLE, "jersey_number")
    player_code_column = await _column_exists(db, PLAYERS_TABLE, "player_code")
    active_column = await _column_exists(db, PLAYERS_TABLE, "active")
    active_sql = "AND p.active = true" if active_column else ""
    jersey_select = "p.jersey_number" if jersey_column else "NULL AS jersey_number"
    player_code_select = "p.player_code" if player_code_column else "NULL AS player_code"

    result = await db.execute(
        text(
            f"""
            SELECT
                p.id,
                p.first_name,
                p.last_name,
                {jersey_select},
                {player_code_select}
            FROM players p
            WHERE p.org_id = :org_id
              {active_sql}
            ORDER BY p.last_name ASC, p.first_name ASC
            """
        ),
        {"org_id": org_id},
    )
    return [dict(row) for row in result.mappings().all()]


def _player_item(row: dict[str, Any], status: str) -> dict[str, Any]:
    name = f"{row['first_name']} {row['last_name']}".strip()
    player_code = row.get("player_code")
    code_value = str(player_code) if player_code is not None else None
    return {
        "id": UUID(str(row["id"])),
        "name": name,
        "code": code_value,
        "player_code": code_value,
        "jersey_number": (
            str(row["jersey_number"]) if row.get("jersey_number") is not None else None
        ),
        "status": status,
    }


def _summary_counts(players: list[dict[str, Any]]) -> dict[str, int]:
    present_count = sum(1 for player in players if player["status"] == ATTENDANCE_STATUS_PRESENT)
    return {
        "present_count": present_count,
        "total_count": len(players),
    }


async def _fetch_attendance_session_row(
    db: AsyncSession,
    user_id: UUID,
) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT id, session_details, status
            FROM practice_sessions
            WHERE recorder_user_id = :user_id
              AND session_date = CURRENT_DATE
              AND status = :status
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"user_id": user_id, "status": SessionStatus.ATTENDANCE.value},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _create_attendance_session(
    db: AsyncSession,
    user: User,
    org_id: UUID,
) -> dict[str, Any]:
    recorder = await coach_identity.ensure_recorder_context(db, user)
    session_id = uuid.uuid4()
    now = _utcnow()
    details = {"attendance": {"players": {}}}

    await db.execute(
        text(
            """
            INSERT INTO practice_sessions (
                id,
                org_id,
                session_date,
                session_details,
                recorder_user_id,
                recorder_coach_id,
                recorder_type,
                status,
                synced,
                created_at
            ) VALUES (
                :id,
                :org_id,
                CURRENT_DATE,
                CAST(:session_details AS jsonb),
                :recorder_user_id,
                :recorder_coach_id,
                'coach',
                :status,
                true,
                :created_at
            )
            """
        ),
        {
            "id": session_id,
            "org_id": org_id,
            "session_details": json.dumps(details),
            "recorder_user_id": user.id,
            "recorder_coach_id": recorder.coach_id,
            "status": SessionStatus.ATTENDANCE.value,
            "created_at": now,
        },
    )
    await db.commit()
    row = await _fetch_attendance_session_row(db, user.id)
    if row is None:
        raise AppException(
            code="ATTENDANCE_SESSION_CREATE_FAILED",
            message="Could not create the attendance session",
            status_code=500,
        )
    return row


async def _get_or_create_attendance_session(
    db: AsyncSession,
    user: User,
    org_id: UUID,
) -> dict[str, Any]:
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)
    row = await _fetch_attendance_session_row(db, user.id)
    if row is not None:
        return row
    return await _create_attendance_session(db, user, org_id)


def _sync_attendance_statuses(
    roster: list[dict[str, Any]],
    attendance_map: dict[str, str],
    *,
    present_player_ids: set[UUID] | None = None,
) -> dict[str, str]:
    """Ensure every active player has an attendance status."""
    synced: dict[str, str] = {}
    present_ids = present_player_ids or set()
    for row in roster:
        player_id = str(row["id"])
        if player_id in attendance_map:
            synced[player_id] = attendance_map[player_id]
        elif player_id in {str(value) for value in present_ids}:
            synced[player_id] = ATTENDANCE_STATUS_PRESENT
        else:
            synced[player_id] = ATTENDANCE_STATUS_ABSENT
    return synced


async def _persist_attendance_map(
    db: AsyncSession,
    session_id: UUID,
    existing_details: dict[str, Any],
    attendance_map: dict[str, str],
) -> None:
    details = _build_attendance_details(existing_details, attendance_map)
    await db.execute(
        text(
            """
            UPDATE practice_sessions
            SET session_details = CAST(:session_details AS jsonb)
            WHERE id = :session_id
            """
        ),
        {
            "session_id": session_id,
            "session_details": json.dumps(details),
        },
    )


async def _build_attendance_player_list(
    db: AsyncSession,
    org_id: UUID,
    attendance_map: dict[str, str],
) -> list[dict[str, Any]]:
    roster = await _fetch_active_players(db, org_id)
    return [
        _player_item(
            row,
            attendance_map.get(str(row["id"]), ATTENDANCE_STATUS_ABSENT),
        )
        for row in roster
    ]


async def _ensure_coach_org(user: User) -> UUID:
    if user.org_id is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Coach must belong to an organization to manage attendance",
            status_code=400,
            details=[
                {
                    "field": "org_id",
                    "message": "Coach must belong to an organization to manage attendance",
                }
            ],
        )
    return user.org_id


async def search_attendance_players(
    db: AsyncSession,
    user: User,
    *,
    search_query: str | None,
    full_name: str | None,
) -> dict[str, Any]:
    """Search active players by name or jersey number with attendance status."""
    org_id = await _ensure_coach_org(user)
    cleaned = resolve_attendance_search_text(search_query=search_query, full_name=full_name)

    session_row = await _get_or_create_attendance_session(db, user, org_id)
    session_details = _parse_session_details(session_row.get("session_details"))
    attendance_map = _attendance_map(session_details)

    jersey_column = await _column_exists(db, PLAYERS_TABLE, "jersey_number")
    player_code_column = await _column_exists(db, PLAYERS_TABLE, "player_code")
    active_column = await _column_exists(db, PLAYERS_TABLE, "active")
    active_sql = "AND p.active = true" if active_column else ""
    jersey_select = "p.jersey_number" if jersey_column else "NULL AS jersey_number"
    player_code_select = "p.player_code" if player_code_column else "NULL AS player_code"
    jersey_filter = "OR p.jersey_number ILIKE :pattern" if jersey_column else ""
    pattern = f"%{cleaned}%"

    result = await db.execute(
        text(
            f"""
            SELECT
                p.id,
                p.first_name,
                p.last_name,
                {jersey_select},
                {player_code_select}
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
        {"org_id": org_id, "pattern": pattern},
    )

    players = [
        _player_item(
            dict(row),
            attendance_map.get(str(row["id"]), ATTENDANCE_STATUS_ABSENT),
        )
        for row in result.mappings().all()
    ]

    logger.info(
        "Attendance search for %r in org %s returned %d players",
        cleaned,
        org_id,
        len(players),
    )
    return {
        "success": True,
        "message": "Players found" if players else "No players matched your search",
        "status": "ready",
        "description": "Matching players for attendance",
        "link": None,
        "error": None,
        "search_query": cleaned,
        "full_name": full_name.strip() if full_name and full_name.strip() else cleaned,
        "players": players,
    }


async def get_attendance_summary(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return attendance summary counts and full active player list."""
    org_id = await _ensure_coach_org(user)
    session_row = await _get_or_create_attendance_session(db, user, org_id)
    session_id = UUID(str(session_row["id"]))
    session_details = _parse_session_details(session_row.get("session_details"))
    attendance_map = _attendance_map(session_details)

    roster = await _fetch_active_players(db, org_id)
    synced_map = _sync_attendance_statuses(roster, attendance_map)
    if synced_map != attendance_map:
        await _persist_attendance_map(db, session_id, session_details, synced_map)
        await db.commit()

    players = [_player_item(row, synced_map[str(row["id"])]) for row in roster]
    summary = _summary_counts(players)

    return {
        "success": True,
        "message": "Attendance summary loaded",
        "status": "ready",
        "description": ATTENDANCE_DESCRIPTION,
        "link": None,
        "error": None,
        "id": session_id,
        "name": "Attendance",
        "title": "Attendance",
        "attendance_summary": summary,
        "players": players,
    }


async def start_attendance_practice(
    db: AsyncSession,
    user: User,
    payload: AttendanceStartPracticeRequest,
) -> dict[str, Any]:
    """Mark present players and transition the attendance session to in progress."""
    org_id = await _ensure_coach_org(user)
    session_row = await _get_or_create_attendance_session(db, user, org_id)
    session_id = UUID(str(session_row["id"]))
    session_details = _parse_session_details(session_row.get("session_details"))
    attendance_map = _attendance_map(session_details)

    roster = await _fetch_active_players(db, org_id)
    roster_ids = {UUID(str(row["id"])) for row in roster}
    present_ids = set(payload.present_player_ids)

    unknown_ids = present_ids - roster_ids
    if unknown_ids:
        raise AppException(
            code="VALIDATION_ERROR",
            message="One or more present players were not found in your active roster",
            status_code=400,
            details=[
                {
                    "field": "present_player_ids",
                    "message": "One or more present players were not found in your active roster",
                }
            ],
        )

    synced_map = _sync_attendance_statuses(
        roster,
        attendance_map,
        present_player_ids=present_ids,
    )
    for player_id in synced_map:
        synced_map[player_id] = (
            ATTENDANCE_STATUS_PRESENT
            if UUID(player_id) in present_ids
            else ATTENDANCE_STATUS_ABSENT
        )

    updated_details = _build_attendance_details(session_details, synced_map)
    now = _utcnow()
    await db.execute(
        text(
            """
            UPDATE practice_sessions
            SET session_details = CAST(:session_details AS jsonb),
                status = :status,
                started_at = :started_at
            WHERE id = :session_id
              AND recorder_user_id = :recorder_user_id
            """
        ),
        {
            "session_id": session_id,
            "session_details": json.dumps(updated_details),
            "status": SessionStatus.IN_PROGRESS.value,
            "started_at": now,
            "recorder_user_id": user.id,
        },
    )
    await db.commit()

    players = [_player_item(row, synced_map[str(row["id"])]) for row in roster]
    summary = _summary_counts(players)

    logger.info(
        "Started attendance practice session %s for coach %s with %d present players",
        session_id,
        user.id,
        summary["present_count"],
    )
    return {
        "success": True,
        "message": "Practice started successfully",
        "status": SessionStatus.IN_PROGRESS.value,
        "description": ATTENDANCE_DESCRIPTION,
        "link": f"{settings.FRONTEND_URL.rstrip('/')}/coach/record",
        "error": None,
        "id": session_id,
        "name": "Attendance",
        "title": "Attendance",
        "session_id": session_id,
        "attendance_summary": summary,
        "players": players,
    }
