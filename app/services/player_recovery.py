"""Player password recovery via email OTP."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import send_password_recovery_email
from app.core.exceptions import AppException
from app.core.security import generate_otp_code, hash_otp, hash_password, otp_matches
from app.models.enums import UserRole
from app.models.user import User
from app.services import auth as auth_service
from app.services.user import validate_password

logger = logging.getLogger(__name__)

_email_adapter = TypeAdapter(EmailStr)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(email: str) -> str:
    """Return a normalized email or raise 400 when empty or invalid."""
    cleaned = (email or "").strip().lower()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Email is required",
            status_code=400,
            details=[{"field": "email", "message": "Email is required"}],
        )
    try:
        return str(_email_adapter.validate_python(cleaned))
    except ValidationError as exc:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid email address",
            status_code=400,
            details=[{"field": "email", "message": "Enter a valid email address"}],
        ) from exc


async def _get_player_by_email(db: AsyncSession, email: str) -> User | None:
    """Return an active player account for the given email, or None when not found."""
    user = await auth_service.get_user_by_email(db, email)
    if user is None or user.role != UserRole.PLAYER.value:
        return None
    if not user.is_active or user.deleted_at is not None:
        return None
    if user.banned_until is not None and user.banned_until > _utcnow():
        return None
    return user


def _recovery_otp_is_expired(user: User) -> bool:
    """Return True when the stored recovery OTP has passed its expiry window."""
    if user.recovery_sent_at is None:
        return True

    sent_at = user.recovery_sent_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    expires_at = sent_at + timedelta(minutes=settings.PASSWORD_RECOVERY_OTP_EXPIRE_MINUTES)
    return _utcnow() > expires_at


def _resend_cooldown_remaining_seconds(user: User) -> int:
    """Return seconds remaining before another recovery code can be sent."""
    if user.recovery_sent_at is None:
        return 0

    sent_at = user.recovery_sent_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    elapsed = (_utcnow() - sent_at).total_seconds()
    remaining = settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed
    return max(0, int(remaining) + (1 if remaining > 0 else 0))


def _validate_verification_code(verification_code: str | None) -> str:
    """Return a normalized 6-digit OTP or raise 400."""
    if verification_code is None or not verification_code.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Verification code is required",
            status_code=400,
            details=[{"field": "verification_code", "message": "Verification code is required"}],
        )

    normalized = verification_code.strip()
    if len(normalized) != 6 or not normalized.isdigit():
        raise AppException(
            code="INVALID_VERIFICATION_CODE",
            message="The verification code is incorrect",
            status_code=400,
            details=[
                {
                    "field": "verification_code",
                    "message": "The verification code is incorrect",
                }
            ],
        )
    return normalized


def _apply_password_reset(
    user: User,
    *,
    password: str | None,
    confirm_password: str | None,
) -> None:
    """Validate and persist a new password when provided on verify-code."""
    if password is None and confirm_password is None:
        return

    if password is None or not password.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password is required",
            status_code=400,
            details=[{"field": "password", "message": "Password is required"}],
        )

    if confirm_password is None or not confirm_password.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Confirm password is required",
            status_code=400,
            details=[{"field": "confirm_password", "message": "Confirm password is required"}],
        )

    cleaned_password = password.strip()
    cleaned_confirm = confirm_password.strip()
    if cleaned_password != cleaned_confirm:
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

    validate_password(cleaned_password)
    user.encrypted_password = hash_password(cleaned_password)


async def request_player_password_recovery(db: AsyncSession, email: str) -> tuple[User, str]:
    """
    Generate and email a recovery OTP for an active player account.

    Returns the user and plaintext OTP (for DEBUG responses only).

    Raises AppException 404 when no player account exists for the email.
    Raises AppException 429 when resend cooldown is active.
    """
    normalized_email = _normalize_email(email)
    user = await _get_player_by_email(db, normalized_email)
    if user is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="We couldn't find an account with that email. Please check the email address and try again.",
            status_code=404,
            details=[
                {
                    "field": "email",
                    "message": "We couldn't find an account with that email. Please check the email address and try again.",
                }
            ],
        )

    cooldown_remaining = _resend_cooldown_remaining_seconds(user)
    if cooldown_remaining > 0 and user.recovery_token is not None:
        raise AppException(
            code="RESEND_COOLDOWN",
            message="Please wait before requesting another verification code",
            status_code=429,
            details=[
                {
                    "field": "email",
                    "message": (
                        f"Please wait {cooldown_remaining} second(s) before requesting "
                        "another verification code"
                    ),
                }
            ],
        )

    otp_code = generate_otp_code()
    now = _utcnow()
    user.recovery_token = hash_otp(otp_code)
    user.recovery_sent_at = now
    user.updated_at = now
    await db.commit()
    await db.refresh(user)

    try:
        send_password_recovery_email(user.email, otp_code)
    except Exception:
        logger.exception("Failed to send password recovery email to %s", user.email)

    logger.info("Sent password recovery code to player user %s", user.id)
    return user, otp_code


async def verify_player_recovery_code(
    db: AsyncSession,
    *,
    email: str,
    verification_code: str | None,
    password: str | None = None,
    confirm_password: str | None = None,
) -> User:
    """
    Verify a password recovery OTP for a player account.

    When ``password`` and ``confirm_password`` are supplied, resets the password
    after successful OTP verification.

    Raises AppException 404 when the email is not registered to a player.
    Raises AppException 400 for invalid or missing verification codes.
    Raises AppException 403 when the recovery code has expired.
    """
    normalized_email = _normalize_email(email)
    normalized_code = _validate_verification_code(verification_code)

    user = await _get_player_by_email(db, normalized_email)
    if user is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="We couldn't find an account with that email. Please check the email address and try again.",
            status_code=404,
            details=[
                {
                    "field": "email",
                    "message": "We couldn't find an account with that email. Please check the email address and try again.",
                }
            ],
        )

    if user.recovery_token is None or user.recovery_sent_at is None:
        raise AppException(
            code="INVALID_VERIFICATION_CODE",
            message="The verification code is incorrect",
            status_code=400,
            details=[
                {
                    "field": "verification_code",
                    "message": "The verification code is incorrect",
                }
            ],
        )

    if _recovery_otp_is_expired(user):
        raise AppException(
            code="RECOVERY_CODE_EXPIRED",
            message="The verification code has expired. Please request a new code.",
            status_code=403,
            details=[
                {
                    "field": "verification_code",
                    "message": "The verification code has expired. Please request a new code.",
                }
            ],
        )

    if not otp_matches(normalized_code, user.recovery_token):
        raise AppException(
            code="INVALID_VERIFICATION_CODE",
            message="The verification code is incorrect",
            status_code=400,
            details=[
                {
                    "field": "verification_code",
                    "message": "The verification code is incorrect",
                }
            ],
        )

    _apply_password_reset(user, password=password, confirm_password=confirm_password)

    now = _utcnow()
    user.recovery_token = None
    user.recovery_sent_at = None
    user.updated_at = now
    await db.commit()
    await db.refresh(user)

    logger.info("Verified password recovery for player user %s", user.id)
    return user
