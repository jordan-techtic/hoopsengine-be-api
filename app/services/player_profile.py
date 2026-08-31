"""Player edit profile service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.player_profile import PlayerProfileUpdateRequest
from app.schemas.profile import CoachProfileUpdateRequest
from app.services import profile as profile_service


async def update_player_profile(
    db: AsyncSession,
    user: User,
    payload: PlayerProfileUpdateRequest,
) -> User:
    """Update the authenticated player's profile fields."""
    coach_payload = CoachProfileUpdateRequest.model_validate(payload.model_dump())
    return await profile_service.update_coach_profile(db, user, coach_payload)


def build_player_profile_response(
    user: User,
    *,
    message: str,
    description: str,
    status: str = "ready",
) -> dict[str, Any]:
    """Map a player user row to the edit profile API envelope."""
    return profile_service.build_coach_profile_response(
        user,
        message=message,
        description=description,
        status=status,
    )
