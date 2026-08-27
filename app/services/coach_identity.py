"""Resolve authenticated coach users to client-domain org/coach records."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User


@dataclass(frozen=True)
class RecorderContext:
    """Org and optional coaches-table identity for session recording."""

    org_id: UUID
    coach_id: UUID | None


def get_coach_org_id(user: User) -> UUID | None:
    """Return the coach user's organization id, if assigned."""
    return user.org_id


async def resolve_recorder_coach_id(db: AsyncSession, user: User) -> UUID | None:
    """Look up a ``coaches`` row matching the user's email within their org."""
    if user.org_id is None or not user.email:
        return None

    row = await db.execute(
        text(
            """
            SELECT id
            FROM coaches
            WHERE org_id = :org_id
              AND email ILIKE :email
            LIMIT 1
            """
        ),
        {"org_id": user.org_id, "email": user.email.strip()},
    )
    coach_id = row.scalar_one_or_none()
    return UUID(str(coach_id)) if coach_id is not None else None


async def ensure_recorder_context(db: AsyncSession, user: User) -> RecorderContext:
    """Build recorder context or raise when the coach lacks an organization."""
    org_id = get_coach_org_id(user)
    if org_id is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Coach must belong to an organization before recording sessions",
            status_code=400,
            details=[
                {
                    "field": "org_id",
                    "message": "Coach must belong to an organization before recording sessions",
                }
            ],
        )

    coach_id = await resolve_recorder_coach_id(db, user)
    return RecorderContext(org_id=org_id, coach_id=coach_id)
