"""Authenticated password reset service for the Player Reset Password screen."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import password_reset as password_reset_service


async def reset_player_password(
    db: AsyncSession,
    *,
    user: User,
    new_password: str | None,
    confirm_password: str | None,
) -> User:
    """
    Reset the authenticated player's password after validating strength and confirmation.

    Client ``phone`` metadata is not persisted for player flows.
    """
    return await password_reset_service.reset_authenticated_password(
        db,
        user=user,
        new_password=new_password,
        confirm_password=confirm_password,
        phone=None,
    )
