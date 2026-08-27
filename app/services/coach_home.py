"""Business logic for coach home screen APIs."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.organization import Organization
from app.models.user import User
from app.services import account_settings, client_db, coach_identity

logger = logging.getLogger(__name__)

NOTIFICATIONS_META_KEY = "home_notifications"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coach_display_name(user: User) -> str:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    full = f"{first} {last}".strip()
    return full or (user.username or "Coach")


async def _get_organization_name(db: AsyncSession, org_id: UUID | None) -> str:
    """Return the organization display name for a coach."""
    if org_id is None:
        return "Organization"
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    return org.name if org is not None else "Organization"


async def _count_active_sessions(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
) -> int:
    """Count active practice sessions recorded by the coach."""
    if not await client_db.table_exists(db, "practice_sessions"):
        return 0
    count = await db.scalar(
        text(
            """
            SELECT COUNT(*)
            FROM practice_sessions
            WHERE org_id = :org_id
              AND recorder_user_id = :user_id
              AND COALESCE(status, 'active') <> 'deleted'
            """
        ),
        {"org_id": org_id, "user_id": user_id},
    )
    return int(count or 0)


async def _count_active_players(db: AsyncSession, *, org_id: UUID) -> int:
    """Count active players in the coach organization."""
    if not await client_db.table_exists(db, "players"):
        return 0
    count = await db.scalar(
        text(
            """
            SELECT COUNT(*)
            FROM players
            WHERE org_id = :org_id
              AND COALESCE(active, true) = true
            """
        ),
        {"org_id": org_id},
    )
    return int(count or 0)


async def _load_recent_activities(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Load recent session-based activities for the coach."""
    if not await client_db.table_exists(db, "practice_sessions"):
        return []

    result = await db.execute(
        text(
            """
            SELECT id, session_mode, created_at, started_at, status
            FROM practice_sessions
            WHERE org_id = :org_id
              AND recorder_user_id = :user_id
              AND COALESCE(status, 'active') <> 'deleted'
            ORDER BY COALESCE(started_at, created_at) DESC NULLS LAST
            LIMIT :limit
            """
        ),
        {"org_id": org_id, "user_id": user_id, "limit": limit},
    )
    activities: list[dict[str, Any]] = []
    for row in result.mappings().all():
        mapping = dict(row)
        mode = str(mapping.get("session_mode") or "session").replace("_", " ").title()
        when = mapping.get("started_at") or mapping.get("created_at") or _utcnow()
        if isinstance(when, datetime) and when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        activities.append(
            {
                "id": mapping.get("id"),
                "description": f"{mode} recorded",
                "timestamp": when,
            }
        )
    return activities


async def _load_attendance_records(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
) -> list[dict[str, str]]:
    """Load attendance records from the coach's most recent session."""
    if not await client_db.table_exists(db, "practice_sessions"):
        return []

    result = await db.execute(
        text(
            """
            SELECT session_details
            FROM practice_sessions
            WHERE org_id = :org_id
              AND recorder_user_id = :user_id
              AND session_details IS NOT NULL
            ORDER BY COALESCE(started_at, created_at) DESC NULLS LAST
            LIMIT 1
            """
        ),
        {"org_id": org_id, "user_id": user_id},
    )
    row = result.mappings().first()
    if row is None:
        return []

    details = row["session_details"]
    if isinstance(details, str):
        details = json.loads(details)
    if not isinstance(details, dict):
        return []

    attendance = details.get("attendance") or {}
    players = attendance.get("players") if isinstance(attendance, dict) else None
    if not isinstance(players, dict):
        return []

    records: list[dict[str, str]] = []
    if await client_db.table_exists(db, "players"):
        for player_id, status in players.items():
            player_result = await db.execute(
                text(
                    """
                    SELECT TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS name
                    FROM players
                    WHERE id = :player_id
                      AND org_id = :org_id
                      AND COALESCE(active, true) = true
                    LIMIT 1
                    """
                ),
                {"player_id": player_id, "org_id": org_id},
            )
            player_row = player_result.mappings().first()
            if player_row is None:
                continue
            name = str(player_row["name"]).strip() or "Player"
            normalized_status = "Present" if str(status).lower() == "present" else "Absent"
            records.append({"player_name": name, "status": normalized_status})
    return records


def _load_notifications(user: User) -> list[dict[str, Any]]:
    """Return stored home notifications from user metadata."""
    meta = account_settings.get_user_meta(user)
    raw = meta.get(NOTIFICATIONS_META_KEY)
    if not isinstance(raw, list):
        return []
    notifications: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text_value = item.get("notification_text") or item.get("text")
        if not text_value:
            continue
        notification_id = item.get("notification_id") or str(uuid4())
        date_raw = item.get("notification_date") or item.get("date")
        if isinstance(date_raw, str):
            try:
                notification_date = datetime.fromisoformat(date_raw)
            except ValueError:
                notification_date = _utcnow()
        elif isinstance(date_raw, datetime):
            notification_date = date_raw
        else:
            notification_date = _utcnow()
        notifications.append(
            {
                "notification_id": UUID(str(notification_id)),
                "notification_text": str(text_value),
                "notification_date": notification_date,
            }
        )
    return notifications


async def get_coach_home(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
    company: str | None = None,
) -> dict[str, Any]:
    """Return aggregated home screen data for the authenticated coach."""
    recorder = await coach_identity.ensure_recorder_context(db, user)
    org_name = await _get_organization_name(db, recorder.org_id)
    total_sessions = await _count_active_sessions(
        db, org_id=recorder.org_id, user_id=user.id
    )
    total_players = await _count_active_players(db, org_id=recorder.org_id)
    recent_activities = await _load_recent_activities(
        db, org_id=recorder.org_id, user_id=user.id, limit=10
    )
    attendance_records = await _load_attendance_records(
        db, org_id=recorder.org_id, user_id=user.id
    )

    logger.info("Loaded coach home data for user %s", user.id)
    coach_name = _coach_display_name(user)
    return {
        "success": True,
        "message": "Home screen loaded successfully",
        "status": "ready",
        "description": None,
        "link": None,
        "error": None,
        "id": user.id,
        "name": coach_name,
        "total_sessions": total_sessions,
        "total_players": total_players,
        "recent_activities": recent_activities,
        "attendance_records": attendance_records,
        "phone": phone,
        "company": company or org_name,
    }


async def get_home_activities(
    db: AsyncSession,
    user: User,
    *,
    limit: int = 10,
) -> dict[str, Any]:
    """Return paginated recent activities for the home screen."""
    recorder = await coach_identity.ensure_recorder_context(db, user)
    raw_activities = await _load_recent_activities(
        db, org_id=recorder.org_id, user_id=user.id, limit=limit
    )
    if not raw_activities:
        raise AppException(
            code="ACTIVITIES_NOT_FOUND",
            message="No activities found for this user",
            status_code=404,
        )

    activities = [
        {
            "activity_id": item.get("id") or uuid4(),
            "activity_text": item["description"],
            "activity_date": item["timestamp"],
            "user_id": user.id,
        }
        for item in raw_activities[:limit]
    ]
    coach_name = _coach_display_name(user)
    return {
        "success": True,
        "message": "Activities loaded successfully",
        "status": "ready",
        "description": None,
        "link": None,
        "error": None,
        "id": user.id,
        "name": coach_name,
        "activities": activities,
        "limit": limit,
        "count": len(activities),
    }


async def get_home_user_info(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return user-specific home screen information."""
    if user.id is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="User not found",
            status_code=404,
        )
    org_name = await _get_organization_name(db, user.org_id)
    coach_name = _coach_display_name(user)
    return {
        "success": True,
        "message": "User info loaded successfully",
        "status": "ready",
        "description": None,
        "link": None,
        "error": None,
        "id": user.id,
        "name": coach_name,
        "user_id": user.id,
        "organization_name": org_name,
        "welcome_message": f"Welcome back, {coach_name}",
    }


async def get_home_notifications(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return notifications for the authenticated coach."""
    notifications = _load_notifications(user)
    if not notifications:
        raise AppException(
            code="NOTIFICATIONS_NOT_FOUND",
            message="No notifications found for this user",
            status_code=404,
        )
    return {
        "success": True,
        "message": "Notifications loaded successfully",
        "status": "ready",
        "description": None,
        "link": None,
        "error": None,
        "id": user.id,
        "name": _coach_display_name(user),
        "notifications": notifications,
    }
