"""Business logic for coach sync activity APIs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.coach_sync_activity import CoachSyncActivitySaveRequest
from app.services import account_settings, client_db, coach_identity, coach_queue

logger = logging.getLogger(__name__)

SYNC_ACTIVITY_META_KEY = "sync_activity_log"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_activity_time(value: datetime | None) -> str:
    """Format an activity timestamp as a short clock time."""
    if value is None:
        return "Now"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    hour = value.strftime("%I").lstrip("0") or "12"
    return f"{hour}:{value.strftime('%M %p')}"


def _queue_status_to_activity_status(queue_status: str) -> str:
    """Map queue statuses to sync activity screen statuses."""
    mapping = {
        "pending_sync": "pending",
        "synced": "success",
        "failed": "pending",
    }
    return mapping.get(queue_status, "pending")


def _load_saved_activities(user: User) -> list[dict[str, str]]:
    """Return saved sync activity rows from user metadata."""
    meta = account_settings.get_user_meta(user)
    raw = meta.get(SYNC_ACTIVITY_META_KEY)
    if not isinstance(raw, list):
        return []
    activities: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict) and item.get("title") and item.get("status"):
            activities.append(
                {
                    "title": str(item["title"]),
                    "time": str(item.get("time") or "Now"),
                    "status": str(item["status"]),
                }
            )
    return activities


def _save_activities(user: User, activities: list[dict[str, str]]) -> None:
    """Persist sync activity rows on the user record."""
    meta = account_settings.get_user_meta(user)
    meta[SYNC_ACTIVITY_META_KEY] = activities
    account_settings.set_user_meta(user, meta)


async def _derive_recent_activities(
    db: AsyncSession,
    user: User,
) -> list[dict[str, str]]:
    """Build recent sync activity rows from queue and recent session records."""
    activities: list[dict[str, str]] = []
    queue = await coach_queue.list_queue_items(db, user)
    for item in queue.get("items") or []:
        activities.append(
            {
                "title": str(item.get("title") or item.get("name") or "Pending sync item"),
                "time": _format_activity_time(_utcnow()),
                "status": _queue_status_to_activity_status(str(item.get("status") or "pending_sync")),
            }
        )

    recorder = await coach_identity.ensure_recorder_context(db, user)
    if await client_db.table_exists(db, "practice_sessions"):
        updated_column = await db.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'practice_sessions'
                      AND column_name = 'updated_at'
                )
                """
            )
        )
        timestamp_column = "updated_at" if updated_column else "created_at"
        result = await db.execute(
            text(
                f"""
                SELECT session_mode, {timestamp_column} AS activity_when, synced
                FROM practice_sessions
                WHERE org_id = :org_id
                  AND recorder_user_id = :user_id
                ORDER BY {timestamp_column} DESC NULLS LAST
                LIMIT 5
                """
            ),
            {"org_id": recorder.org_id, "user_id": user.id},
        )
        for row in result.mappings().all():
            mapping = dict(row)
            synced = bool(mapping.get("synced"))
            mode = str(mapping.get("session_mode") or "session").replace("_", " ").title()
            activities.append(
                {
                    "title": (
                        f"{mode} synced successfully"
                        if synced
                        else f"{mode} waiting for connection"
                    ),
                    "time": _format_activity_time(mapping.get("activity_when")),
                    "status": "success" if synced else "pending",
                }
            )

    if not activities:
        activities.append(
            {
                "title": "Auto-sync completed",
                "time": _format_activity_time(_utcnow()),
                "status": "completed",
            }
        )
    return activities[:10]


def _status_card(activities: list[dict[str, str]]) -> tuple[str, str | None]:
    """Derive status card title and subtitle for the Sync Activity screen."""
    if not activities:
        return "Sync Activity", "No recent sync activity available"

    pending_count = sum(1 for item in activities if item.get("status") == "pending")
    if pending_count:
        return (
            "Sync Activity",
            f"{pending_count} item(s) waiting to sync",
        )

    return "All Synced", "All recordings are up to date"


async def get_sync_activity(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return recent sync activity for the authenticated coach."""
    saved = _load_saved_activities(user)
    activities = saved or await _derive_recent_activities(db, user)
    title, description = _status_card(activities)
    return {
        "success": True,
        "message": "Sync activity loaded successfully",
        "status": "ready",
        "description": description,
        "link": None,
        "error": None,
        "id": user.id,
        "title": title,
        "recent_activities": activities,
        "save_status": "success",
        "phone": phone,
    }


async def save_sync_activity(
    db: AsyncSession,
    user: User,
    payload: CoachSyncActivitySaveRequest,
) -> dict[str, Any]:
    """Persist sync activity updates submitted by the coach."""
    if not payload.recent_activities:
        raise AppException(
            code="VALIDATION_ERROR",
            message="recent_activities is required",
            status_code=400,
            details=[
                {
                    "field": "recent_activities",
                    "message": "At least one activity is required",
                }
            ],
        )

    activities = [
        {
            "title": item.title.strip(),
            "time": item.time.strip(),
            "status": item.status,
        }
        for item in payload.recent_activities
        if item.title.strip()
    ]
    if not activities:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Each activity must include a title",
            status_code=400,
            details=[{"field": "recent_activities", "message": "Activity title is required"}],
        )

    _save_activities(user, activities)
    await db.commit()
    await db.refresh(user)
    logger.info("Coach %s saved %d sync activity rows", user.id, len(activities))
    title, description = _status_card(activities)
    return {
        "success": True,
        "message": "Sync activity saved successfully",
        "status": "saved",
        "description": description,
        "link": None,
        "error": None,
        "id": user.id,
        "title": title,
        "save_status": "success",
        "recent_activities": activities,
        "phone": payload.phone,
    }
