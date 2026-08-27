"""Cancel and continue verification flow for coach/player signup."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_verification_in_progress(user: User) -> None:
    """Raise 409 when verification cannot be cancelled or continued."""
    if user.email_confirmed_at is not None:
        raise AppException(
            code="VERIFICATION_ALREADY_COMPLETED",
            message="Your email has already been verified",
            status_code=409,
            details=[
                {
                    "field": "email",
                    "message": "Verification has already been completed",
                }
            ],
        )

    if not user.confirmation_token:
        raise AppException(
            code="VERIFICATION_NOT_IN_PROGRESS",
            message="No verification process is currently in progress",
            status_code=409,
            details=[
                {
                    "field": "cancel_verification",
                    "message": "Verification is not in progress or has already been cancelled",
                }
            ],
        )


async def cancel_verification(
    db: AsyncSession,
    *,
    user: User,
    phone: str | None = None,
) -> User:
    """
    Cancel the authenticated user's pending email verification and soft-delete the account.

    Clears OTP state and marks the user inactive so signup progress is lost.
    """
    _ensure_verification_in_progress(user)

    now = _utcnow()
    user.confirmation_token = None
    user.confirmation_sent_at = None
    user.deleted_at = now
    user.is_active = False
    if phone is not None:
        cleaned_phone = phone.strip()
        user.phone = cleaned_phone or user.phone

    await db.commit()
    await db.refresh(user)
    return user


async def continue_verification(
    db: AsyncSession,
    *,
    user: User,
) -> User:
    """Return the authenticated user's pending verification state."""
    _ensure_verification_in_progress(user)
    return user
