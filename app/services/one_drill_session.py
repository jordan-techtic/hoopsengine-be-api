"""Business logic for One Drill Step-3 session management."""

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
from app.models.enums import SessionMode, SessionStatus
from app.models.user import User
from app.schemas.one_drill_session import OneDrillSessionCreateRequest, OneDrillSessionUpdateRequest
from app.services import client_db, coach_identity
from app.services.one_drill_flow import ONE_DRILL_FLOW_KEY, _json_dumps, _merge_flow_details

logger = logging.getLogger(__name__)

PLAYERS_TABLE = "players"
DRILLS_TABLE = "drills"
SESSION_DATA_TABLE = "session_data"
FREE_THROW_CATEGORY_PATTERN = "%free%throw%"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_non_empty(value: str, field: str, label: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{label} is required",
            status_code=400,
            details=[{"field": field, "message": f"{label} is required"}],
        )
    return cleaned


def _validate_metric_counts(
    *,
    makes: int,
    attempts: int,
    free_throws_makes: int,
    free_throws_attempts: int,
) -> None:
    details: list[dict[str, str]] = []
    if makes > attempts:
        details.append(
            {
                "field": "makes",
                "message": "Makes cannot exceed attempts",
            }
        )
    if free_throws_makes > free_throws_attempts:
        details.append(
            {
                "field": "free_throws_makes",
                "message": "Free throw makes cannot exceed free throw attempts",
            }
        )
    if details:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Session metrics are invalid",
            status_code=400,
            details=details,
        )


async def _fetch_player_by_name(
    db: AsyncSession,
    *,
    org_id: UUID,
    player_name: str,
) -> dict[str, Any]:
    await client_db.require_table(db, PLAYERS_TABLE)
    result = await db.execute(
        text(
            """
            SELECT id, first_name, last_name, org_id
            FROM players
            WHERE org_id = :org_id
              AND LOWER(
                    TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))
                  ) = LOWER(:player_name)
            LIMIT 1
            """
        ),
        {"org_id": org_id, "player_name": player_name.strip()},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[{"field": "player", "message": "Player not found in your organization"}],
        )
    return dict(row)


async def _fetch_drill_by_name(db: AsyncSession, drill_name: str) -> dict[str, Any]:
    await client_db.require_table(db, DRILLS_TABLE)
    result = await db.execute(
        text(
            """
            SELECT id, name, category
            FROM drills
            WHERE LOWER(name) = LOWER(:drill_name)
            LIMIT 1
            """
        ),
        {"drill_name": drill_name.strip()},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="DRILL_NOT_FOUND",
            message="Drill not found",
            status_code=404,
            details=[{"field": "drill", "message": "Drill not found"}],
        )
    return dict(row)


async def _fetch_free_throw_drill(db: AsyncSession) -> dict[str, Any] | None:
    result = await db.execute(
        text(
            """
            SELECT id, name, category
            FROM drills
            WHERE LOWER(category) LIKE :pattern
            ORDER BY name
            LIMIT 1
            """
        ),
        {"pattern": FREE_THROW_CATEGORY_PATTERN},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _fetch_owned_session(
    db: AsyncSession,
    session_id: UUID,
    user: User,
) -> dict[str, Any]:
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)
    result = await db.execute(
        text(
            """
            SELECT
                id,
                org_id,
                session_mode,
                session_details,
                status,
                recorder_user_id
            FROM practice_sessions
            WHERE id = :session_id
            """
        ),
        {"session_id": session_id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="SESSION_NOT_FOUND",
            message="Session not found",
            status_code=404,
        )
    mapping = dict(row)
    owner_id = mapping.get("recorder_user_id")
    if owner_id is None or UUID(str(owner_id)) != user.id:
        raise AppException(
            code="SESSION_ACCESS_FORBIDDEN",
            message="You do not have permission to access this session",
            status_code=403,
        )
    return mapping


async def _upsert_session_data_row(
    db: AsyncSession,
    *,
    session_id: UUID,
    org_id: UUID,
    player_id: UUID,
    drill_id: UUID,
    makes: int,
    attempts: int,
    synced: bool = True,
) -> None:
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return

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
    row_id = existing.scalar_one_or_none()
    if row_id is not None:
        await db.execute(
            text(
                """
                UPDATE session_data
                SET makes = :makes,
                    attempts = :attempts,
                    recorded_at = NOW(),
                    synced = :synced
                WHERE id = :id
                """
            ),
            {"id": row_id, "makes": makes, "attempts": attempts, "synced": synced},
        )
        return

    await db.execute(
        text(
            """
            INSERT INTO session_data (
                id, session_id, org_id, player_id, drill_id, makes, attempts, synced
            ) VALUES (
                :id, :session_id, :org_id, :player_id, :drill_id, :makes, :attempts, :synced
            )
            """
        ),
        {
            "id": uuid.uuid4(),
            "session_id": session_id,
            "org_id": org_id,
            "player_id": player_id,
            "drill_id": drill_id,
            "makes": makes,
            "attempts": attempts,
            "synced": synced,
        },
    )


async def _load_session_metrics(
    db: AsyncSession,
    *,
    session_id: UUID,
    player_id: UUID,
    drill_id: UUID,
    free_throw_drill_id: UUID | None,
) -> tuple[int, int, int, int]:
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return 0, 0, 0, 0

    main_result = await db.execute(
        text(
            """
            SELECT makes, attempts
            FROM session_data
            WHERE session_id = :session_id
              AND player_id = :player_id
              AND drill_id = :drill_id
            LIMIT 1
            """
        ),
        {"session_id": session_id, "player_id": player_id, "drill_id": drill_id},
    )
    main_row = main_result.mappings().first()
    makes = int(main_row["makes"] or 0) if main_row else 0
    attempts = int(main_row["attempts"] or 0) if main_row else 0

    ft_makes = 0
    ft_attempts = 0
    if free_throw_drill_id is not None:
        ft_result = await db.execute(
            text(
                """
                SELECT makes, attempts
                FROM session_data
                WHERE session_id = :session_id
                  AND player_id = :player_id
                  AND drill_id = :drill_id
                LIMIT 1
                """
            ),
            {
                "session_id": session_id,
                "player_id": player_id,
                "drill_id": free_throw_drill_id,
            },
        )
        ft_row = ft_result.mappings().first()
        if ft_row is not None:
            ft_makes = int(ft_row["makes"] or 0)
            ft_attempts = int(ft_row["attempts"] or 0)

    return makes, attempts, ft_makes, ft_attempts


def _player_display_name(row: dict[str, Any]) -> str:
    return f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()


def _session_response(
    *,
    session_id: UUID,
    player_name: str,
    drill_name: str,
    makes: int,
    attempts: int,
    free_throws_makes: int,
    free_throws_attempts: int,
    message: str,
    status: str = "saved",
) -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "status": status,
        "description": "One Drill session metrics recorded",
        "link": f"{settings.API_V1_PREFIX}/sessions/summary",
        "error": None,
        "id": session_id,
        "player": player_name,
        "drill": drill_name,
        "makes": makes,
        "attempts": attempts,
        "free_throws_makes": free_throws_makes,
        "free_throws_attempts": free_throws_attempts,
    }


async def _resolve_context_ids(
    db: AsyncSession,
    session_row: dict[str, Any],
) -> tuple[UUID, UUID, str, str, UUID | None]:
    """Resolve player/drill ids and names from session_details or session_data."""
    details_raw = session_row.get("session_details")
    if isinstance(details_raw, str):
        details = json.loads(details_raw)
    elif isinstance(details_raw, dict):
        details = details_raw
    else:
        details = {}

    flow = details.get(ONE_DRILL_FLOW_KEY, {}) if isinstance(details, dict) else {}
    player_id = flow.get("player_id") or flow.get("selected_player_id")
    drill_id = flow.get("drill_id") or flow.get("selected_drill_id")
    player_name = flow.get("player_name") or flow.get("player")
    drill_name = flow.get("drill_name") or flow.get("drill")

    session_id = UUID(str(session_row["id"]))

    if player_id and drill_id:
        player_uuid = UUID(str(player_id))
        drill_uuid = UUID(str(drill_id))
        if not player_name or not drill_name:
            player_row = await db.execute(
                text("SELECT first_name, last_name FROM players WHERE id = :id"),
                {"id": player_uuid},
            )
            player_mapping = player_row.mappings().first()
            if player_mapping and not player_name:
                player_name = _player_display_name(dict(player_mapping))

            drill_row = await db.execute(
                text("SELECT name FROM drills WHERE id = :id"),
                {"id": drill_uuid},
            )
            drill_mapping = drill_row.mappings().first()
            if drill_mapping and not drill_name:
                drill_name = str(drill_mapping["name"])

        ft_drill = await _fetch_free_throw_drill(db)
        ft_drill_id = UUID(str(ft_drill["id"])) if ft_drill else None
        return (
            player_uuid,
            drill_uuid,
            str(player_name or ""),
            str(drill_name or ""),
            ft_drill_id,
        )

    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        raise AppException(
            code="SESSION_NOT_FOUND",
            message="Session metrics not found",
            status_code=404,
        )

    result = await db.execute(
        text(
            """
            SELECT
                sd.player_id,
                sd.drill_id,
                TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, '')) AS player_name,
                d.name AS drill_name,
                d.category
            FROM session_data sd
            JOIN players p ON p.id = sd.player_id
            JOIN drills d ON d.id = sd.drill_id
            WHERE sd.session_id = :session_id
              AND LOWER(d.category) NOT LIKE :free_throw_pattern
            ORDER BY sd.recorded_at DESC NULLS LAST
            LIMIT 1
            """
        ),
        {"session_id": session_id, "free_throw_pattern": FREE_THROW_CATEGORY_PATTERN},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="SESSION_NOT_FOUND",
            message="Session metrics not found",
            status_code=404,
        )
    ft_drill = await _fetch_free_throw_drill(db)
    return (
        UUID(str(row["player_id"])),
        UUID(str(row["drill_id"])),
        str(row["player_name"]).strip(),
        str(row["drill_name"]),
        UUID(str(ft_drill["id"])) if ft_drill else None,
    )


async def create_one_drill_session(
    db: AsyncSession,
    user: User,
    payload: OneDrillSessionCreateRequest,
) -> dict[str, Any]:
    """Create a One Drill session with player, drill, and performance metrics."""
    player_name = _require_non_empty(payload.player, "player", "Player")
    drill_name = _require_non_empty(payload.drill, "drill", "Drill")
    _validate_metric_counts(
        makes=payload.makes,
        attempts=payload.attempts,
        free_throws_makes=payload.free_throws_makes,
        free_throws_attempts=payload.free_throws_attempts,
    )

    recorder = await coach_identity.ensure_recorder_context(db, user)
    player_row = await _fetch_player_by_name(db, org_id=recorder.org_id, player_name=player_name)
    drill_row = await _fetch_drill_by_name(db, drill_name)
    player_id = UUID(str(player_row["id"]))
    drill_id = UUID(str(drill_row["id"]))

    session_id = uuid.uuid4()
    now = _utcnow()
    details = _merge_flow_details(
        {},
        {
            "step": 3,
            "player_id": str(player_id),
            "drill_id": str(drill_id),
            "player_name": player_name,
            "drill_name": drill_name,
            "selected_player_id": str(player_id),
            "selected_drill_id": str(drill_id),
        },
    )

    await db.execute(
        text(
            """
            INSERT INTO practice_sessions (
                id,
                org_id,
                session_date,
                session_mode,
                session_details,
                recorder_user_id,
                recorder_coach_id,
                recorder_type,
                status,
                started_at,
                synced,
                created_at
            ) VALUES (
                :id,
                :org_id,
                CURRENT_DATE,
                :session_mode,
                CAST(:session_details AS jsonb),
                :recorder_user_id,
                :recorder_coach_id,
                'coach',
                :status,
                :started_at,
                true,
                :created_at
            )
            """
        ),
        {
            "id": session_id,
            "org_id": recorder.org_id,
            "session_mode": SessionMode.ONE_DRILL.value,
            "session_details": _json_dumps(details),
            "recorder_user_id": user.id,
            "recorder_coach_id": recorder.coach_id,
            "status": SessionStatus.IN_PROGRESS.value,
            "started_at": now,
            "created_at": now,
        },
    )

    await _upsert_session_data_row(
        db,
        session_id=session_id,
        org_id=recorder.org_id,
        player_id=player_id,
        drill_id=drill_id,
        makes=payload.makes,
        attempts=payload.attempts,
    )

    if payload.free_throws_makes > 0 or payload.free_throws_attempts > 0:
        ft_drill = await _fetch_free_throw_drill(db)
        if ft_drill is not None:
            await _upsert_session_data_row(
                db,
                session_id=session_id,
                org_id=recorder.org_id,
                player_id=player_id,
                drill_id=UUID(str(ft_drill["id"])),
                makes=payload.free_throws_makes,
                attempts=payload.free_throws_attempts,
            )

    await db.commit()
    logger.info("Created One Drill session %s for coach %s", session_id, user.id)
    return _session_response(
        session_id=session_id,
        player_name=player_name,
        drill_name=drill_name,
        makes=payload.makes,
        attempts=payload.attempts,
        free_throws_makes=payload.free_throws_makes,
        free_throws_attempts=payload.free_throws_attempts,
        message="Session created successfully",
        status="saved",
    )


async def get_one_drill_session(
    db: AsyncSession,
    user: User,
    session_id: UUID,
) -> dict[str, Any]:
    """Return One Drill Step-3 session detail for the authenticated coach."""
    session_row = await _fetch_owned_session(db, session_id, user)
    player_id, drill_id, player_name, drill_name, ft_drill_id = await _resolve_context_ids(
        db, session_row
    )
    makes, attempts, ft_makes, ft_attempts = await _load_session_metrics(
        db,
        session_id=session_id,
        player_id=player_id,
        drill_id=drill_id,
        free_throw_drill_id=ft_drill_id,
    )
    return _session_response(
        session_id=session_id,
        player_name=player_name,
        drill_name=drill_name,
        makes=makes,
        attempts=attempts,
        free_throws_makes=ft_makes,
        free_throws_attempts=ft_attempts,
        message="Session loaded successfully",
        status=str(session_row.get("status") or SessionStatus.IN_PROGRESS.value),
    )


async def update_one_drill_session(
    db: AsyncSession,
    user: User,
    session_id: UUID,
    payload: OneDrillSessionUpdateRequest,
) -> dict[str, Any]:
    """Update One Drill session metrics for an existing session."""
    if (
        payload.makes is None
        and payload.attempts is None
        and payload.free_throws_makes is None
        and payload.free_throws_attempts is None
    ):
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one metric field must be provided",
            status_code=400,
            details=[
                {
                    "field": "makes",
                    "message": "Provide makes, attempts, and/or free throw metrics to update",
                }
            ],
        )

    session_row = await _fetch_owned_session(db, session_id, user)
    org_id = UUID(str(session_row["org_id"]))
    player_id, drill_id, player_name, drill_name, ft_drill_id = await _resolve_context_ids(
        db, session_row
    )
    makes, attempts, ft_makes, ft_attempts = await _load_session_metrics(
        db,
        session_id=session_id,
        player_id=player_id,
        drill_id=drill_id,
        free_throw_drill_id=ft_drill_id,
    )

    new_makes = payload.makes if payload.makes is not None else makes
    new_attempts = payload.attempts if payload.attempts is not None else attempts
    new_ft_makes = (
        payload.free_throws_makes if payload.free_throws_makes is not None else ft_makes
    )
    new_ft_attempts = (
        payload.free_throws_attempts
        if payload.free_throws_attempts is not None
        else ft_attempts
    )
    _validate_metric_counts(
        makes=new_makes,
        attempts=new_attempts,
        free_throws_makes=new_ft_makes,
        free_throws_attempts=new_ft_attempts,
    )

    await _upsert_session_data_row(
        db,
        session_id=session_id,
        org_id=org_id,
        player_id=player_id,
        drill_id=drill_id,
        makes=new_makes,
        attempts=new_attempts,
    )

    if new_ft_makes > 0 or new_ft_attempts > 0:
        ft_drill = await _fetch_free_throw_drill(db)
        if ft_drill is not None:
            await _upsert_session_data_row(
                db,
                session_id=session_id,
                org_id=org_id,
                player_id=player_id,
                drill_id=UUID(str(ft_drill["id"])),
                makes=new_ft_makes,
                attempts=new_ft_attempts,
            )

    await db.commit()
    logger.info("Updated One Drill session %s for coach %s", session_id, user.id)
    return _session_response(
        session_id=session_id,
        player_name=player_name,
        drill_name=drill_name,
        makes=new_makes,
        attempts=new_attempts,
        free_throws_makes=new_ft_makes,
        free_throws_attempts=new_ft_attempts,
        message="Session updated successfully",
        status=str(session_row.get("status") or SessionStatus.IN_PROGRESS.value),
    )


async def list_one_drill_sessions_summary(
    db: AsyncSession,
    user: User,
) -> dict[str, Any]:
    """Return a summary list of the coach's One Drill sessions."""
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)

    result = await db.execute(
        text(
            """
            SELECT id, status, session_details
            FROM practice_sessions
            WHERE recorder_user_id = :user_id
              AND session_mode = :session_mode
            ORDER BY created_at DESC
            """
        ),
        {"user_id": user.id, "session_mode": SessionMode.ONE_DRILL.value},
    )
    sessions: list[dict[str, Any]] = []
    for row in result.mappings().all():
        session_row = dict(row)
        session_id = UUID(str(session_row["id"]))
        try:
            player_id, drill_id, player_name, drill_name, ft_drill_id = await _resolve_context_ids(
                db, session_row
            )
            makes, attempts, ft_makes, ft_attempts = await _load_session_metrics(
                db,
                session_id=session_id,
                player_id=player_id,
                drill_id=drill_id,
                free_throw_drill_id=ft_drill_id,
            )
        except AppException:
            continue

        sessions.append(
            {
                "id": session_id,
                "player": player_name,
                "drill": drill_name,
                "makes": makes,
                "attempts": attempts,
                "free_throws_makes": ft_makes,
                "free_throws_attempts": ft_attempts,
                "status": str(session_row.get("status") or SessionStatus.IN_PROGRESS.value),
            }
        )

    return {
        "success": True,
        "message": "Session summaries loaded successfully",
        "status": "ready",
        "description": "Review saved One Drill sessions",
        "link": None,
        "error": None,
        "id": sessions[0]["id"] if sessions else None,
        "sessions": sessions,
    }
