"""One Drill multi-step flow state stored on practice_sessions.session_details."""

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
from app.schemas.coach_drill_flow import (
    CoachDrillContinueRequest,
    CoachDrillSearchRequest,
    CoachDrillSelectPlayerRequest,
)
from app.services import client_db, coach_identity
from app.services.player import search_players

logger = logging.getLogger(__name__)

ONE_DRILL_FLOW_KEY = "one_drill_flow"
ACTIVE_SESSION_STATUSES = (
    SessionStatus.SELECTING_MODE.value,
    SessionStatus.IN_PROGRESS.value,
)


def _parse_session_details(raw: Any) -> dict[str, Any]:
    """Return session_details as a dict."""
    if raw is None:
        return {}
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def _flow_block(details: dict[str, Any]) -> dict[str, Any]:
    """Return the nested one_drill_flow block."""
    block = details.get(ONE_DRILL_FLOW_KEY)
    return dict(block) if isinstance(block, dict) else {}


def _json_dumps(data: dict[str, Any]) -> str:
    """Serialize session details with UUID-safe encoding."""

    def _default(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    return json.dumps(data, default=_default)


def _merge_flow_details(existing: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Merge patch values into session_details.one_drill_flow."""
    merged = dict(existing)
    flow = _flow_block(merged)
    flow.update(patch)
    merged[ONE_DRILL_FLOW_KEY] = flow
    return merged


async def _fetch_active_one_drill_session(
    db: AsyncSession,
    user_id: UUID,
) -> dict[str, Any] | None:
    """Load the coach's active one_drill session for today, if any."""
    result = await db.execute(
        text(
            """
            SELECT id, session_details, session_mode, status
            FROM practice_sessions
            WHERE recorder_user_id = :user_id
              AND session_date = CURRENT_DATE
              AND session_mode = :session_mode
              AND status IN ('selecting_mode', 'in_progress')
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"user_id": user_id, "session_mode": SessionMode.ONE_DRILL.value},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _persist_session_details(
    db: AsyncSession,
    session_id: UUID,
    details: dict[str, Any],
) -> None:
    """Update practice_sessions.session_details JSONB."""
    await db.execute(
        text(
            """
            UPDATE practice_sessions
            SET session_details = CAST(:session_details AS jsonb)
            WHERE id = :session_id
            """
        ),
        {"session_id": session_id, "session_details": _json_dumps(details)},
    )


async def get_or_create_one_drill_session(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return today's active one_drill session or create a minimal in-progress row."""
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)
    recorder = await coach_identity.ensure_recorder_context(db, user)

    existing = await _fetch_active_one_drill_session(db, user.id)
    if existing is not None:
        return existing

    session_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    details = _merge_flow_details({}, {"step": 1})

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
    await db.commit()

    row = await _fetch_active_one_drill_session(db, user.id)
    if row is None:
        raise AppException(
            code="ONE_DRILL_SESSION_CREATE_FAILED",
            message="Could not start the One Drill session",
            status_code=500,
        )
    return row


async def search_players_for_drill(
    db: AsyncSession,
    user: User,
    payload: CoachDrillSearchRequest,
) -> dict[str, Any]:
    """Search org players by name or jersey number for One Drill Step-1."""
    result = await search_players(
        db,
        user,
        search_query=payload.search_query,
        full_name=payload.full_name,
        phone=payload.phone,
    )
    return {
        "success": True,
        "message": result["message"],
        "status": result["status"],
        "description": result["description"],
        "link": None,
        "error": None,
        "search_query": result["search_query"],
        "full_name": result.get("full_name"),
        "players": result["players"],
    }


async def _assert_player_in_org(
    db: AsyncSession,
    *,
    org_id: UUID,
    player_id: UUID,
) -> dict[str, Any]:
    """Return the player row when active in the coach org or raise 409."""
    await client_db.require_table(db, "players")
    active_column = await db.scalar(
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
    active_sql = "AND active = true" if active_column else ""
    result = await db.execute(
        text(
            f"""
            SELECT id, first_name, last_name, org_id
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
            message="Selected player is not available in your organization",
            status_code=409,
            details=[
                {
                    "field": "selected_player_id",
                    "message": "Selected player is not available in your organization",
                }
            ],
        )
    return dict(row)


async def select_player(
    db: AsyncSession,
    user: User,
    payload: CoachDrillSelectPlayerRequest,
) -> dict[str, Any]:
    """Persist the selected player on the active One Drill session."""
    recorder = await coach_identity.ensure_recorder_context(db, user)
    player_row = await _assert_player_in_org(
        db,
        org_id=recorder.org_id,
        player_id=payload.selected_player_id,
    )

    session_row = await get_or_create_one_drill_session(db, user)
    session_id = UUID(str(session_row["id"]))
    details = _parse_session_details(session_row.get("session_details"))
    player_name = f"{player_row['first_name']} {player_row['last_name']}".strip()

    updated_details = _merge_flow_details(
        details,
        {
            "step": 1,
            "selected_player_id": str(payload.selected_player_id),
            "player_name": player_name,
        },
    )
    await _persist_session_details(db, session_id, updated_details)
    await db.commit()

    logger.info(
        "Coach %s selected player %s for One Drill session %s",
        user.id,
        payload.selected_player_id,
        session_id,
    )
    return {
        "success": True,
        "message": "Player selected successfully",
        "status": "ready",
        "description": "Continue to select a drill",
        "link": f"{settings.API_V1_PREFIX}/coach/drills/continue",
        "error": None,
        "selected_player_id": payload.selected_player_id,
    }


async def continue_to_next_step(
    db: AsyncSession,
    user: User,
    payload: CoachDrillContinueRequest,
) -> dict[str, Any]:
    """Advance the One Drill flow to Step 2 after player selection."""
    _ = payload.phone  # client metadata only
    session_row = await get_or_create_one_drill_session(db, user)
    session_id = UUID(str(session_row["id"]))
    details = _parse_session_details(session_row.get("session_details"))
    flow = _flow_block(details)

    if flow.get("selected_player_id") is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Select a player before continuing",
            status_code=400,
            details=[
                {
                    "field": "selected_player_id",
                    "message": "Select a player before continuing to the next step",
                }
            ],
        )

    updated_details = _merge_flow_details(details, {"step": 2})
    await _persist_session_details(db, session_id, updated_details)
    await db.commit()

    base = settings.FRONTEND_URL.rstrip("/")
    logger.info("Coach %s advanced One Drill session %s to step 2", user.id, session_id)
    return {
        "success": True,
        "message": "Ready to select a drill",
        "status": "ready",
        "description": "Step 2: Select Drill",
        "link": f"{base}/coach/record/one-drill/step-2",
        "error": None,
        "step": 2,
    }


async def continue_with_selected_drill(
    db: AsyncSession,
    user: User,
    selected_drill_id: UUID,
) -> dict[str, Any]:
    """Persist selected drill on the active One Drill session and advance to step 3."""
    session_row = await get_or_create_one_drill_session(db, user)
    session_id = UUID(str(session_row["id"]))
    details = _parse_session_details(session_row.get("session_details"))
    flow = _flow_block(details)

    if flow.get("selected_player_id") is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Select a player before choosing a drill",
            status_code=400,
            details=[
                {
                    "field": "selected_player_id",
                    "message": "Complete Step 1 player selection before continuing",
                }
            ],
        )

    updated_details = _merge_flow_details(
        details,
        {
            "step": 3,
            "selected_drill_id": str(selected_drill_id),
        },
    )
    await _persist_session_details(db, session_id, updated_details)
    await db.commit()

    base = settings.FRONTEND_URL.rstrip("/")
    logger.info(
        "Coach %s continued One Drill flow with drill %s on session %s",
        user.id,
        selected_drill_id,
        session_id,
    )
    return {
        "success": True,
        "message": "Drill selected successfully",
        "status": "ready",
        "description": "Proceed to record session metrics",
        "link": f"{base}/coach/record/one-drill/step-3",
        "error": None,
        "selected_drill_id": selected_drill_id,
        "step": 3,
    }
