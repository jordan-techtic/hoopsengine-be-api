"""Authenticated password reset service for the Coach Reset Password screen."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.services.user import (
    analyze_password_strength,
    is_password_strong,
    validate_password,
)


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


def evaluate_password_strength(password: str) -> dict[str, bool]:
    """Return the password strength checklist for the validate endpoint."""
    return analyze_password_strength(password)


async def reset_authenticated_password(
    db: AsyncSession,
    *,
    user: User,
    new_password: str | None,
    confirm_password: str | None,
    phone: str | None = None,
) -> User:
    """
    Reset the authenticated user's password after validating strength and confirmation.

    Raises 400 for empty, weak, or mismatched passwords.
    Raises 409 when the new password matches the current password.
    """
    cleaned_new = _ensure_non_empty(new_password, field="new_password", label="New password")
    cleaned_confirm = _ensure_non_empty(
        confirm_password,
        field="confirm_password",
        label="Confirm password",
    )

    if cleaned_new != cleaned_confirm:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Passwords do not match",
            status_code=400,
            details=[
                {
                    "field": "confirm_password",
                    "message": "Passwords do not match",
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
    if phone is not None:
        cleaned_phone = phone.strip()
        if cleaned_phone:
            user.phone = cleaned_phone

    await db.commit()
    await db.refresh(user)
    return user


def validate_password_for_reset(password: str | None) -> tuple[dict[str, bool], bool]:
    """
    Validate password strength for the GET validate endpoint.

    Raises 400 when password is missing or empty.
    """
    cleaned = _ensure_non_empty(password, field="password", label="Password")
    requirements = evaluate_password_strength(cleaned)
    return requirements, is_password_strong(cleaned)
