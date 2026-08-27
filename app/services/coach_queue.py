"""Business logic for coach sync queue APIs."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.coach_queue import (
    QUEUE_ITEM_TYPES,
    QUEUE_STATUSES,
    CoachQueueUpdateRequest,
)
from app.services import client_db, coach_identity

logger = logging.getLogger(__name__)

PRACTICE_SESSIONS_TABLE = "practice_sessions"
SESSION_DATA_TABLE = "session_data"


def _coach_display_name(user: User) -> str:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    full = f"{first} {last}".strip()
    return full or (user.username or "Coach")


def _format_queue_date(value: date | datetime | None) -> str:
    if value is None:
        return "Unknown Date"
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%b %d")


def _session_mode_label(session_mode: str | None) -> str:
    mapping = {
        "one_drill": "One Drill Session",
        "daily_options": "Daily Options Session",
        "practice_plan": "Practice Plan Session",
    }
    if session_mode:
        normalized = session_mode.strip().lower()
        if normalized in mapping:
            return mapping[normalized]
        return session_mode.replace("_", " ").title()
    return "Training Session"


def _build_title(name: str, when: date | datetime | None) -> str:
    return f"{name} - {_format_queue_date(when)}"


def _pending_title(count: int) -> str:
    label = "Item" if count == 1 else "Items"
    return f"{count} {label} Pending Sync"


def _validate_status_filter(status_filter: str | None) -> str | None:
    if status_filter is None or not status_filter.strip():
        return None
    cleaned = status_filter.strip().lower()
    if cleaned not in {"pending_sync", "synced", "all"}:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid status_filter value",
            status_code=400,
            details=[
                {
                    "field": "status_filter",
                    "message": "status_filter must be pending_sync, synced, or all",
                }
            ],
        )
    return cleaned


def _validate_item_type(item_type: str) -> str:
    cleaned = (item_type or "").strip().lower()
    if cleaned not in QUEUE_ITEM_TYPES:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid item_type value",
            status_code=400,
            details=[
                {
                    "field": "item_type",
                    "message": "item_type must be practice_session or session_data",
                }
            ],
        )
    return cleaned


def _validate_queue_status(status: str) -> str:
    cleaned = (status or "").strip().lower()
    if cleaned not in QUEUE_STATUSES:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid queue status value",
            status_code=400,
            details=[
                {
                    "field": "status",
                    "message": "status must be pending_sync, synced, or failed",
                }
            ],
        )
    return cleaned


def _queue_item(
    *,
    item_id: UUID,
    title: str,
    name: str,
    status: str,
    item_type: str,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "title": title,
        "name": name,
        "status": status,
        "item_type": item_type,
    }


async def _fetch_pending_practice_sessions(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
) -> list[dict[str, Any]]:
    if not await client_db.table_exists(db, PRACTICE_SESSIONS_TABLE):
        return []

    synced_column = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'practice_sessions'
                  AND column_name = 'synced'
            )
            """
        )
    )
    if not synced_column:
        return []

    result = await db.execute(
        text(
            """
            SELECT id, session_mode, session_date, status
            FROM practice_sessions
            WHERE org_id = :org_id
              AND recorder_user_id = :user_id
              AND synced = false
            ORDER BY session_date DESC, created_at DESC
            """
        ),
        {"org_id": org_id, "user_id": user_id},
    )
    items: list[dict[str, Any]] = []
    for row in result.mappings().all():
        mapping = dict(row)
        label = _session_mode_label(mapping.get("session_mode"))
        when = mapping.get("session_date")
        items.append(
            _queue_item(
                item_id=UUID(str(mapping["id"])),
                title=_build_title(label, when),
                name=label,
                status="pending_sync",
                item_type="practice_session",
            )
        )
    return items


async def _fetch_pending_session_data(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
) -> list[dict[str, Any]]:
    if not await client_db.table_exists(db, SESSION_DATA_TABLE):
        return []

    synced_column = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'session_data'
                  AND column_name = 'synced'
            )
            """
        )
    )
    if not synced_column:
        return []

    result = await db.execute(
        text(
            """
            SELECT
                sd.id,
                sd.session_date,
                sd.recorded_at,
                d.name AS drill_name,
                ps.session_mode
            FROM session_data sd
            LEFT JOIN drills d ON d.id = sd.drill_id
            LEFT JOIN practice_sessions ps ON ps.id = sd.session_id
            WHERE sd.org_id = :org_id
              AND sd.synced = false
              AND (
                    ps.recorder_user_id = :user_id
                 OR ps.recorder_user_id IS NULL
              )
            ORDER BY sd.recorded_at DESC NULLS LAST, sd.session_date DESC
            """
        ),
        {"org_id": org_id, "user_id": user_id},
    )
    items: list[dict[str, Any]] = []
    for row in result.mappings().all():
        mapping = dict(row)
        drill_name = mapping.get("drill_name")
        if drill_name:
            label = str(drill_name)
        else:
            label = _session_mode_label(mapping.get("session_mode"))
            if label == "Training Session":
                label = "Session Metrics"
        when = mapping.get("session_date") or mapping.get("recorded_at")
        items.append(
            _queue_item(
                item_id=UUID(str(mapping["id"])),
                title=_build_title(label, when),
                name=label,
                status="pending_sync",
                item_type="session_data",
            )
        )
    return items


async def list_queue_items(
    db: AsyncSession,
    user: User,
    *,
    status_filter: str | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return queue items pending synchronization for the authenticated coach."""
    _ = phone
    validated_filter = _validate_status_filter(status_filter)
    recorder = await coach_identity.ensure_recorder_context(db, user)

    if validated_filter == "synced":
        items: list[dict[str, Any]] = []
    else:
        session_items = await _fetch_pending_practice_sessions(
            db, org_id=recorder.org_id, user_id=user.id
        )
        data_items = await _fetch_pending_session_data(
            db, org_id=recorder.org_id, user_id=user.id
        )
        items = session_items + data_items

    pending_count = len(items)
    coach_name = _coach_display_name(user)
    logger.info("Loaded %d queue items for coach %s", pending_count, user.id)

    return {
        "success": True,
        "message": "Queue loaded successfully" if items else "No items pending sync",
        "status": "ready",
        "description": "Will sync automatically when connected to an internet network.",
        "link": None,
        "error": None,
        "title": _pending_title(pending_count),
        "name": coach_name,
        "id": items[0]["id"] if items else None,
        "pending_count": pending_count,
        "items": items,
    }


async def _update_practice_session_status(
    db: AsyncSession,
    *,
    item_id: UUID,
    org_id: UUID,
    user_id: UUID,
    status: str,
) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            SELECT id, session_mode, session_date
            FROM practice_sessions
            WHERE id = :item_id
              AND org_id = :org_id
              AND recorder_user_id = :user_id
            LIMIT 1
            """
        ),
        {"item_id": item_id, "org_id": org_id, "user_id": user_id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="QUEUE_ITEM_NOT_FOUND",
            message="Queue item not found",
            status_code=404,
        )

    mapping = dict(row)
    synced = status == "synced"
    await db.execute(
        text(
            """
            UPDATE practice_sessions
            SET synced = :synced
            WHERE id = :item_id
            """
        ),
        {"item_id": item_id, "synced": synced},
    )

    label = _session_mode_label(mapping.get("session_mode"))
    return {
        "title": _build_title(label, mapping.get("session_date")),
        "name": label,
        "status": status,
    }


async def _update_session_data_status(
    db: AsyncSession,
    *,
    item_id: UUID,
    org_id: UUID,
    user_id: UUID,
    status: str,
) -> dict[str, Any]:
    result = await db.execute(
        text(
            """
            SELECT
                sd.id,
                sd.session_date,
                sd.recorded_at,
                d.name AS drill_name,
                ps.session_mode,
                ps.recorder_user_id
            FROM session_data sd
            LEFT JOIN drills d ON d.id = sd.drill_id
            LEFT JOIN practice_sessions ps ON ps.id = sd.session_id
            WHERE sd.id = :item_id
              AND sd.org_id = :org_id
            LIMIT 1
            """
        ),
        {"item_id": item_id, "org_id": org_id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="QUEUE_ITEM_NOT_FOUND",
            message="Queue item not found",
            status_code=404,
        )

    mapping = dict(row)
    owner_id = mapping.get("recorder_user_id")
    if owner_id is not None and UUID(str(owner_id)) != user_id:
        raise AppException(
            code="QUEUE_ITEM_NOT_FOUND",
            message="Queue item not found",
            status_code=404,
        )

    synced = status == "synced"
    await db.execute(
        text(
            """
            UPDATE session_data
            SET synced = :synced,
                recorded_at = NOW()
            WHERE id = :item_id
            """
        ),
        {"item_id": item_id, "synced": synced},
    )

    drill_name = mapping.get("drill_name")
    if drill_name:
        label = str(drill_name)
    else:
        label = _session_mode_label(mapping.get("session_mode"))
        if label == "Training Session":
            label = "Session Metrics"

    when = mapping.get("session_date") or mapping.get("recorded_at")
    return {
        "title": _build_title(label, when),
        "name": label,
        "status": status,
    }


async def update_queue_item(
    db: AsyncSession,
    user: User,
    payload: CoachQueueUpdateRequest,
) -> dict[str, Any]:
    """Update sync status for a queue item owned by the authenticated coach."""
    _ = payload.phone
    item_type = _validate_item_type(payload.item_type)
    status = _validate_queue_status(payload.status)
    recorder = await coach_identity.ensure_recorder_context(db, user)

    if item_type == "practice_session":
        await client_db.require_table(db, PRACTICE_SESSIONS_TABLE)
        updated = await _update_practice_session_status(
            db,
            item_id=payload.item_id,
            org_id=recorder.org_id,
            user_id=user.id,
            status=status,
        )
    else:
        await client_db.require_table(db, SESSION_DATA_TABLE)
        updated = await _update_session_data_status(
            db,
            item_id=payload.item_id,
            org_id=recorder.org_id,
            user_id=user.id,
            status=status,
        )

    await db.commit()
    logger.info(
        "Coach %s updated queue item %s (%s) to %s",
        user.id,
        payload.item_id,
        item_type,
        status,
    )
    return {
        "success": True,
        "message": "Queue item updated successfully",
        "status": updated["status"],
        "description": (
            "Item removed from the pending sync queue"
            if status == "synced"
            else "Queue item status updated"
        ),
        "link": f"{settings.API_V1_PREFIX}/coach/queue",
        "error": None,
        "id": payload.item_id,
        "title": updated["title"],
        "name": updated["name"],
    }
