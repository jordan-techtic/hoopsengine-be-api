"""Business logic for coach offline sync APIs."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.coach_sync import CoachSyncPreferencesUpdateRequest
from app.services import account_settings, client_db, coach_identity, coach_queue

logger = logging.getLogger(__name__)

AUTO_SYNC_META_KEY = "auto_sync_enabled"
SYNC_FREQUENCY_MINUTES_META_KEY = "sync_frequency_minutes"
LAST_SYNCED_META_KEY = "last_synced_at"
SYNC_IN_PROGRESS_META_KEY = "sync_in_progress"
DEFAULT_SYNC_FREQUENCY_MINUTES = 15
SYNC_FREQUENCY_PATTERN = re.compile(r"(\d+)")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_sync_frequency(minutes: int) -> str:
    """Format stored minutes as a human-readable sync frequency label."""
    return f"Every {minutes} minutes"


def _format_last_synced(value: datetime | None) -> str | None:
    """Format last synced timestamp for the mobile client."""
    if value is None:
        return None
    now = _utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if value.date() == now.date():
        hour = value.strftime("%I").lstrip("0") or "12"
        return f"Today, {hour}:{value.strftime('%M %p')}"
    return value.strftime("%b %d, %Y %I:%M %p").lstrip("0")


def parse_sync_frequency_minutes(value: str | None) -> int:
    """Parse sync frequency from numeric or label input."""
    if value is None or not str(value).strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Sync frequency is required",
            status_code=400,
            details=[{"field": "sync_frequency", "message": "Sync frequency cannot be empty"}],
        )

    cleaned = str(value).strip()
    if cleaned.isdigit():
        minutes = int(cleaned)
    else:
        match = SYNC_FREQUENCY_PATTERN.search(cleaned)
        if match is None:
            raise AppException(
                code="VALIDATION_ERROR",
                message="Sync frequency must include a numeric value",
                status_code=400,
                details=[
                    {
                        "field": "sync_frequency",
                        "message": "Sync frequency must be numeric or include minutes",
                    }
                ],
            )
        minutes = int(match.group(1))

    if minutes <= 0:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Sync frequency must be greater than zero",
            status_code=400,
            details=[{"field": "sync_frequency", "message": "Sync frequency must be numeric"}],
        )
    return minutes


def _get_sync_preferences(user: User) -> dict[str, Any]:
    """Read sync preference values from user metadata."""
    meta = account_settings.get_user_meta(user)
    minutes = meta.get(SYNC_FREQUENCY_MINUTES_META_KEY, DEFAULT_SYNC_FREQUENCY_MINUTES)
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        minutes = DEFAULT_SYNC_FREQUENCY_MINUTES

    last_synced_raw = meta.get(LAST_SYNCED_META_KEY)
    last_synced: datetime | None = None
    if isinstance(last_synced_raw, str) and last_synced_raw.strip():
        try:
            last_synced = datetime.fromisoformat(last_synced_raw)
        except ValueError:
            last_synced = None

    return {
        "auto_sync": bool(meta.get(AUTO_SYNC_META_KEY, True)),
        "sync_frequency_minutes": minutes,
        "last_synced": last_synced,
        "sync_in_progress": bool(meta.get(SYNC_IN_PROGRESS_META_KEY, False)),
    }


def _set_sync_preferences(user: User, **updates: Any) -> None:
    """Persist sync preference values on the user row."""
    meta = account_settings.get_user_meta(user)
    if "auto_sync" in updates and updates["auto_sync"] is not None:
        meta[AUTO_SYNC_META_KEY] = bool(updates["auto_sync"])
    if "sync_frequency_minutes" in updates and updates["sync_frequency_minutes"] is not None:
        meta[SYNC_FREQUENCY_MINUTES_META_KEY] = int(updates["sync_frequency_minutes"])
    if "last_synced" in updates:
        value = updates["last_synced"]
        meta[LAST_SYNCED_META_KEY] = value.isoformat() if isinstance(value, datetime) else None
    if "sync_in_progress" in updates and updates["sync_in_progress"] is not None:
        meta[SYNC_IN_PROGRESS_META_KEY] = bool(updates["sync_in_progress"])
    account_settings.set_user_meta(user, meta)


async def _count_pending_uploads(db: AsyncSession, user: User) -> int:
    """Count queue items pending synchronization for the coach."""
    queue = await coach_queue.list_queue_items(db, user)
    return int(queue.get("pending_count") or 0)


async def _mark_all_pending_synced(db: AsyncSession, user: User) -> int:
    """Mark all pending queue records as synced for the authenticated coach."""
    recorder = await coach_identity.ensure_recorder_context(db, user)
    updated = 0

    if await client_db.table_exists(db, "practice_sessions"):
        result = await db.execute(
            text(
                """
                UPDATE practice_sessions
                SET synced = true
                WHERE org_id = :org_id
                  AND recorder_user_id = :user_id
                  AND synced = false
                """
            ),
            {"org_id": recorder.org_id, "user_id": user.id},
        )
        updated += int(result.rowcount or 0)

    if await client_db.table_exists(db, "session_data"):
        result = await db.execute(
            text(
                """
                UPDATE session_data sd
                SET synced = true,
                    recorded_at = NOW()
                FROM practice_sessions ps
                WHERE sd.session_id = ps.id
                  AND sd.org_id = :org_id
                  AND sd.synced = false
                  AND ps.recorder_user_id = :user_id
                """
            ),
            {"org_id": recorder.org_id, "user_id": user.id},
        )
        updated += int(result.rowcount or 0)

    return updated


async def build_preferences_response(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
    local_storage_used: str | None = None,
    message: str = "Sync preferences loaded successfully",
) -> dict[str, Any]:
    """Build sync preferences payload for GET/PUT responses."""
    prefs = _get_sync_preferences(user)
    pending_uploads = await _count_pending_uploads(db, user)
    return {
        "success": True,
        "message": message,
        "status": "ready",
        "description": None,
        "link": None,
        "error": None,
        "id": user.id,
        "auto_sync": prefs["auto_sync"],
        "sync_frequency": _format_sync_frequency(prefs["sync_frequency_minutes"]),
        "last_synced": _format_last_synced(prefs["last_synced"]),
        "pending_uploads": pending_uploads,
        "local_storage_used": local_storage_used,
        "phone": phone,
    }


async def get_sync_preferences(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
    local_storage_used: str | None = None,
) -> dict[str, Any]:
    """Return current sync preferences for the authenticated coach."""
    return await build_preferences_response(
        db,
        user,
        phone=phone,
        local_storage_used=local_storage_used,
    )


async def update_sync_preferences(
    db: AsyncSession,
    user: User,
    payload: CoachSyncPreferencesUpdateRequest,
) -> dict[str, Any]:
    """Update sync preferences for the authenticated coach."""
    updates: dict[str, Any] = {}
    if payload.auto_sync is not None:
        updates["auto_sync"] = payload.auto_sync
    if payload.sync_frequency is not None:
        updates["sync_frequency_minutes"] = parse_sync_frequency_minutes(payload.sync_frequency)

    if not updates:
        raise AppException(
            code="VALIDATION_ERROR",
            message="No sync preference fields provided",
            status_code=400,
            details=[{"field": "sync_frequency", "message": "Provide auto_sync or sync_frequency"}],
        )

    _set_sync_preferences(user, **updates)
    await db.commit()
    await db.refresh(user)
    logger.info("Updated sync preferences for coach %s", user.id)
    return await build_preferences_response(
        db,
        user,
        phone=payload.phone,
        message="Sync preferences updated successfully",
    )


async def trigger_sync(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Trigger the sync process for the authenticated coach."""
    _ = phone
    prefs = _get_sync_preferences(user)
    if prefs["sync_in_progress"]:
        raise AppException(
            code="SYNC_IN_PROGRESS",
            message="A sync operation is already in progress",
            status_code=409,
        )

    _set_sync_preferences(user, sync_in_progress=True)
    await db.commit()

    try:
        synced_count = await _mark_all_pending_synced(db, user)
        now = _utcnow()
        _set_sync_preferences(user, last_synced=now, sync_in_progress=False)
        await db.commit()
        await db.refresh(user)
    except Exception:
        _set_sync_preferences(user, sync_in_progress=False)
        await db.commit()
        raise

    logger.info("Coach %s synced %d pending records", user.id, synced_count)
    return {
        "success": True,
        "message": "Sync completed successfully",
        "status": "completed",
        "description": f"Synchronized {synced_count} pending item(s)",
        "link": None,
        "error": None,
        "id": user.id,
    }


async def clear_local_cache(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Acknowledge local cache clearing and reset sync-in-progress state."""
    _ = phone
    _set_sync_preferences(user, sync_in_progress=False)
    await db.commit()
    await db.refresh(user)
    logger.info("Coach %s cleared local cache metadata", user.id)
    return {
        "success": True,
        "message": "Local cache cleared successfully",
        "status": "ready",
        "description": "Server-side sync metadata has been reset",
        "link": None,
        "error": None,
        "id": user.id,
    }
