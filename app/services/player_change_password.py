"""Business logic for authenticated player change-password."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.services.user import validate_password

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_non_empty(value: str | None, *, field: str, label: str) -> str:
    if value is None or not value.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{label} is required",
            status_code=400,
            details=[{"field": field, "message": f"{label} is required"}],
        )
    return value.strip()


async def change_player_password(
    db: AsyncSession,
    user: User,
    *,
    current_password: str | None,
    new_password: str | None,
    confirm_new_password: str | None,
) -> User:
    """
    Change the authenticated player's password after verifying the current password.

    Raises 400 for empty, incorrect, or weak passwords.
    Raises 409 when confirmation does not match or the new password matches the current password.
    """
    current = _ensure_non_empty(
        current_password,
        field="current_password",
        label="Current password",
    )
    cleaned_new = _ensure_non_empty(
        new_password,
        field="new_password",
        label="New password",
    )
    cleaned_confirm = _ensure_non_empty(
        confirm_new_password,
        field="confirm_new_password",
        label="Confirm new password",
    )

    if not verify_password(current, user.encrypted_password):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Current password is incorrect",
            status_code=400,
            details=[{"field": "current_password", "message": "Current password is incorrect"}],
        )

    if cleaned_new != cleaned_confirm:
        raise AppException(
            code="PASSWORD_MISMATCH",
            message="New password and confirmation do not match",
            status_code=409,
            details=[
                {
                    "field": "confirm_new_password",
                    "message": "New password and confirmation do not match",
                }
            ],
        )

    validate_password(cleaned_new)

    if verify_password(cleaned_new, user.encrypted_password):
        raise AppException(
            code="PASSWORD_UNCHANGED",
            message="New password must be different from your current password",
            status_code=409,
            details=[
                {
                    "field": "new_password",
                    "message": "New password must be different from your current password",
                }
            ],
        )

    user.encrypted_password = hash_password(cleaned_new)
    user.recovery_token = None
    user.recovery_sent_at = None
    user.updated_at = _utcnow()
    await db.commit()
    await db.refresh(user)
    logger.info("Player %s changed password", user.id)
    return user
