"""Email verification OTP service for coach accounts."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import send_verification_email
from app.core.exceptions import AppException
from app.core.security import generate_otp_code, hash_otp, otp_matches
from app.models.user import User
from app.services import auth as auth_service

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _ensure_not_already_verified(user: User) -> None:
    """Raise 409 when the user's email has already been verified."""
    if user.email_confirmed_at is not None:
        raise AppException(
            code="EMAIL_ALREADY_VERIFIED",
            message="This email address has already been verified",
            status_code=409,
            details=[
                {
                    "field": "email",
                    "message": "This email address has already been verified",
                }
            ],
        )


async def _resolve_email_for_request(
    db: AsyncSession,
    *,
    current_user: User,
    request_email: str | None,
) -> str:
    """
    Resolve and validate the email for verify/resend requests.

    Uses the JWT user's email when the body omits email. When provided, the
    email must match the authenticated user or belong to a registered account.
    """
    if request_email is None or not request_email.strip():
        return current_user.email

    normalized = _normalize_email(request_email)
    if normalized == current_user.email:
        return normalized

    registered = await auth_service.get_user_by_email(db, normalized)
    if registered is None:
        raise AppException(
            code="EMAIL_NOT_REGISTERED",
            message="We couldn't find an account with that email address",
            status_code=400,
            details=[
                {
                    "field": "email",
                    "message": "We couldn't find an account with that email address",
                }
            ],
        )

    if registered.id != current_user.id:
        raise AppException(
            code="EMAIL_NOT_REGISTERED",
            message="We couldn't find an account with that email address",
            status_code=400,
            details=[
                {
                    "field": "email",
                    "message": "We couldn't find an account with that email address",
                }
            ],
        )

    return normalized


def _otp_is_expired(user: User) -> bool:
    """Return True when the stored OTP has passed its expiry window."""
    if user.confirmation_sent_at is None:
        return True

    sent_at = user.confirmation_sent_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    expires_at = sent_at + timedelta(minutes=settings.EMAIL_VERIFICATION_OTP_EXPIRE_MINUTES)
    return _utcnow() > expires_at


def _resend_cooldown_remaining_seconds(user: User) -> int:
    """Return seconds remaining before another resend is allowed, or 0 if allowed."""
    if user.confirmation_sent_at is None:
        return 0

    sent_at = user.confirmation_sent_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    elapsed = (_utcnow() - sent_at).total_seconds()
    remaining = settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed
    return max(0, int(remaining) + (1 if remaining > 0 else 0))


async def verify_email_otp(
    db: AsyncSession,
    *,
    current_user: User,
    otp_code: str | None,
    request_email: str | None = None,
) -> User:
    """
    Verify the user's email using a 6-digit OTP code.

    Raises AppException for validation failures (400), already verified (409),
    and expired or incorrect codes (400).
    """
    await _resolve_email_for_request(db, current_user=current_user, request_email=request_email)
    _ensure_not_already_verified(current_user)

    if otp_code is None or not otp_code.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Verification code is required",
            status_code=400,
            details=[{"field": "otp_code", "message": "Verification code is required"}],
        )

    normalized_otp = otp_code.strip()
    if len(normalized_otp) != 6 or not normalized_otp.isdigit():
        raise AppException(
            code="INVALID_OTP",
            message="The verification code is incorrect",
            status_code=400,
            details=[{"field": "otp_code", "message": "The verification code is incorrect"}],
        )

    if current_user.confirmation_token is None or current_user.confirmation_sent_at is None:
        raise AppException(
            code="INVALID_OTP",
            message="The verification code is incorrect",
            status_code=400,
            details=[{"field": "otp_code", "message": "The verification code is incorrect"}],
        )

    if _otp_is_expired(current_user):
        raise AppException(
            code="OTP_EXPIRED",
            message="The verification code has expired. Please request a new code.",
            status_code=400,
            details=[
                {
                    "field": "otp_code",
                    "message": "The verification code has expired. Please request a new code.",
                }
            ],
        )

    if not otp_matches(normalized_otp, current_user.confirmation_token):
        raise AppException(
            code="INVALID_OTP",
            message="The verification code is incorrect",
            status_code=400,
            details=[{"field": "otp_code", "message": "The verification code is incorrect"}],
        )

    now = _utcnow()
    current_user.email_confirmed_at = now
    current_user.confirmation_token = None
    current_user.confirmation_sent_at = None
    current_user.updated_at = now
    await db.commit()
    await db.refresh(current_user)

    logger.info("Verified email for user %s", current_user.id)
    return current_user


async def resend_verification_code(
    db: AsyncSession,
    *,
    current_user: User,
    request_email: str | None = None,
) -> User:
    """
    Generate and email a new verification OTP for the authenticated user.

    Raises AppException when already verified (409), email is not registered (400),
    or resend is requested too frequently (429).
    """
    await _resolve_email_for_request(db, current_user=current_user, request_email=request_email)
    _ensure_not_already_verified(current_user)

    cooldown_remaining = _resend_cooldown_remaining_seconds(current_user)
    if cooldown_remaining > 0:
        raise AppException(
            code="RESEND_COOLDOWN",
            message="Please wait before requesting another verification code",
            status_code=429,
            details=[
                {
                    "field": "otp_code",
                    "message": (
                        f"Please wait {cooldown_remaining} second(s) before requesting "
                        "another verification code"
                    ),
                }
            ],
        )

    otp_code = generate_otp_code()
    now = _utcnow()
    current_user.confirmation_token = hash_otp(otp_code)
    current_user.confirmation_sent_at = now
    current_user.updated_at = now
    await db.commit()
    await db.refresh(current_user)

    try:
        send_verification_email(current_user.email, otp_code)
    except Exception:
        logger.exception("Failed to resend verification email to %s", current_user.email)

    logger.info("Resent verification code to user %s", current_user.id)
    return current_user
