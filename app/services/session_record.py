"""Business logic for coach session mode selection and recording."""

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
from app.schemas.session_record import (
    SessionDetailsInput,
    SessionModeItem,
    SessionRecordCreateRequest,
    SessionRecordUpdateRequest,
)
from app.services import client_db, coach_identity

logger = logging.getLogger(__name__)

ACTIVE_SESSION_STATUSES = (
    SessionStatus.SELECTING_MODE.value,
    SessionStatus.IN_PROGRESS.value,
)

SESSION_MODES: tuple[SessionModeItem, ...] = (
    SessionModeItem(
        mode=SessionMode.ONE_DRILL,
        label="One Drill",
        description="Focus on a single drill and track reps, time, or performance",
    ),
    SessionModeItem(
        mode=SessionMode.DAILY_OPTIONS,
        label="Daily Options",
        description="Pick from today's recommended drills and exercises",
    ),
    SessionModeItem(
        mode=SessionMode.PRACTICE_PLAN,
        label="Practice Plan",
        description="Follow a structured plan with multiple drills in sequence",
    ),
)

_MODE_BY_VALUE = {item.mode.value: item for item in SESSION_MODES}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_session_modes() -> list[SessionModeItem]:
    """Return the static list of supported session recording modes."""
    return list(SESSION_MODES)


def get_mode_or_404(mode: str) -> SessionModeItem:
    """Return a session mode item or raise 404 when the mode is unknown."""
    normalized = mode.strip().lower()
    item = _MODE_BY_VALUE.get(normalized)
    if item is None:
        raise AppException(
            code="SESSION_MODE_NOT_FOUND",
            message="Session mode not found",
            status_code=404,
        )
    return item


def _details_to_dict(details: SessionDetailsInput | None) -> dict[str, Any] | None:
    """Convert nested session details input to a JSON-serializable dict."""
    if details is None:
        return None
    payload = details.model_dump(exclude_none=True)
    return payload or None


def _row_to_response(row: dict[str, Any], *, message: str) -> dict[str, Any]:
    """Map a practice_sessions row dict to the API response envelope."""
    mode_item = get_mode_or_404(str(row["session_mode"]))
    session_details = row.get("session_details")
    if isinstance(session_details, str):
        session_details = json.loads(session_details)

    description = None
    if isinstance(session_details, dict):
        description = session_details.get("description")
    if not description:
        description = mode_item.description

    status = row.get("status") or SessionStatus.IN_PROGRESS.value
    link = None
    if status != SessionStatus.COMPLETED.value:
        link = f"{settings.FRONTEND_URL.rstrip('/')}/coach/record/attendance"

    return {
        "success": True,
        "message": message,
        "status": status,
        "description": description,
        "link": link,
        "error": None,
        "id": row["id"],
        "session_mode": mode_item.mode,
        "session_details": session_details,
        "created_at": row.get("created_at"),
    }


async def _fetch_session_row(db: AsyncSession, session_id: UUID) -> dict[str, Any] | None:
    """Load a practice session row by primary key."""
    result = await db.execute(
        text(
            """
            SELECT
                id,
                session_mode,
                session_details,
                status,
                created_at,
                recorder_user_id
            FROM practice_sessions
            WHERE id = :session_id
            """
        ),
        {"session_id": session_id},
    )
    mapping = result.mappings().first()
    return dict(mapping) if mapping is not None else None


async def _has_active_session_today(db: AsyncSession, user_id: UUID) -> bool:
    """Return True when the coach already has an active session for today."""
    result = await db.execute(
        text(
            """
            SELECT id
            FROM practice_sessions
            WHERE recorder_user_id = :user_id
              AND session_date = CURRENT_DATE
              AND status IN ('selecting_mode', 'in_progress')
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    )
    return result.scalar_one_or_none() is not None


async def create_session_record(
    db: AsyncSession,
    user: User,
    payload: SessionRecordCreateRequest,
) -> dict[str, Any]:
    """Create a new practice session after the coach selects a recording mode."""
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)
    get_mode_or_404(payload.session_mode.value)

    recorder = await coach_identity.ensure_recorder_context(db, user)

    if await _has_active_session_today(db, user.id):
        raise AppException(
            code="SESSION_MODE_ALREADY_RECORDED",
            message="An active session mode is already recorded for today",
            status_code=409,
            details=[
                {
                    "field": "session_mode",
                    "message": "An active session mode is already recorded for today",
                }
            ],
        )

    session_id = uuid.uuid4()
    now = _utcnow()
    details = _details_to_dict(payload.session_details)

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
            "session_mode": payload.session_mode.value,
            "session_details": json.dumps(details) if details is not None else None,
            "recorder_user_id": user.id,
            "recorder_coach_id": recorder.coach_id,
            "status": SessionStatus.IN_PROGRESS.value,
            "started_at": now,
            "created_at": now,
        },
    )
    await db.commit()

    row = await _fetch_session_row(db, session_id)
    if row is None:
        raise AppException(
            code="SESSION_CREATE_FAILED",
            message="Could not create the session record",
            status_code=500,
        )

    logger.info("Created practice session %s for coach user %s", session_id, user.id)
    return _row_to_response(row, message="Session mode recorded successfully")


async def update_session_record(
    db: AsyncSession,
    user: User,
    session_id: UUID,
    payload: SessionRecordUpdateRequest,
) -> dict[str, Any]:
    """Update an existing practice session owned by the authenticated coach."""
    await client_db.require_table(db, client_db.PRACTICE_SESSIONS_TABLE)

    if payload.session_mode is None and payload.session_details is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one field must be provided to update the session record",
            status_code=400,
            details=[
                {
                    "field": "session_mode",
                    "message": "Provide session_mode and/or session_details to update",
                }
            ],
        )

    existing = await _fetch_session_row(db, session_id)
    existing_owner = existing.get("recorder_user_id") if existing else None
    if (
        existing is None
        or existing_owner is None
        or UUID(str(existing_owner)) != user.id
    ):
        raise AppException(
            code="SESSION_NOT_FOUND",
            message="Session record not found",
            status_code=404,
        )

    if payload.session_mode is not None:
        get_mode_or_404(payload.session_mode.value)

    set_clauses: list[str] = []
    params: dict[str, Any] = {"session_id": session_id}

    if payload.session_mode is not None:
        set_clauses.append("session_mode = :session_mode")
        params["session_mode"] = payload.session_mode.value

    if payload.session_details is not None:
        details = _details_to_dict(payload.session_details)
        set_clauses.append("session_details = CAST(:session_details AS jsonb)")
        params["session_details"] = json.dumps(details) if details is not None else None

    await db.execute(
        text(
            f"""
            UPDATE practice_sessions
            SET {", ".join(set_clauses)}
            WHERE id = :session_id
              AND recorder_user_id = :recorder_user_id
            """
        ),
        {**params, "recorder_user_id": user.id},
    )
    await db.commit()

    row = await _fetch_session_row(db, session_id)
    if row is None:
        raise AppException(
            code="SESSION_NOT_FOUND",
            message="Session record not found",
            status_code=404,
        )

    logger.info("Updated practice session %s for coach user %s", session_id, user.id)
    return _row_to_response(row, message="Session record updated successfully")
