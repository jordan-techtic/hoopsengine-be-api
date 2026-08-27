"""Coach self-registration service."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import send_verification_email
from app.core.exceptions import AppException
from app.core.security import (
    create_access_token,
    generate_otp_code,
    hash_otp,
    hash_password,
)
from app.models.user import User
from app.services import auth as auth_service
from app.services import role_selection as role_selection_service
from app.services.user import display_name, validate_password

logger = logging.getLogger(__name__)

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class RegisterResult:
    """Successful coach registration payload returned to the route layer."""

    user: User
    access_token: str
    expires_in_hours: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_non_empty(value: str, field: str) -> str:
    """Return a trimmed non-empty string or raise a 400 validation error."""
    cleaned = value.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{field.replace('_', ' ').title()} is required",
            status_code=400,
            details=[{"field": field, "message": f"{field.replace('_', ' ').title()} is required"}],
        )
    return cleaned


def validate_username(username: str) -> str:
    """Validate coach username format and length. Raises 400 when invalid."""
    cleaned = _require_non_empty(username, "username")
    if len(cleaned) > 30:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Username must be at most 30 characters",
            status_code=400,
            details=[{"field": "username", "message": "Username must be at most 30 characters"}],
        )
    if not USERNAME_PATTERN.match(cleaned):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Username may only contain letters, numbers, and underscores",
            status_code=400,
            details=[
                {
                    "field": "username",
                    "message": "Username may only contain letters, numbers, and underscores",
                }
            ],
        )
    return cleaned


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Look up a non-deleted user by username (case-sensitive storage)."""
    result = await db.execute(
        select(User).where(
            User.username == username.strip(),
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def register_coach(
    db: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    username: str,
    email: str,
    password: str,
    confirm_password: str,
    terms_accepted: bool,
    phone: str | None = None,
    session_token: UUID | None = None,
) -> RegisterResult:
    """
    Register a new coach account, send a verification OTP email, and return a JWT.

    Raises AppException with 400 for validation failures and 409 for duplicate
    email or username.
    """
    if not terms_accepted:
        raise AppException(
            code="VALIDATION_ERROR",
            message="You must accept the terms and conditions to register",
            status_code=400,
            details=[
                {
                    "field": "terms_accepted",
                    "message": "You must accept the terms and conditions to register",
                }
            ],
        )

    if password != confirm_password:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password and confirm password do not match",
            status_code=400,
            details=[
                {
                    "field": "confirm_password",
                    "message": "Password and confirm password do not match",
                }
            ],
        )

    normalized_first_name = _require_non_empty(first_name, "first_name")
    normalized_last_name = _require_non_empty(last_name, "last_name")
    if len(normalized_first_name) > 50:
        raise AppException(
            code="VALIDATION_ERROR",
            message="First name must be at most 50 characters",
            status_code=400,
            details=[{"field": "first_name", "message": "First name must be at most 50 characters"}],
        )
    if len(normalized_last_name) > 50:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Last name must be at most 50 characters",
            status_code=400,
            details=[{"field": "last_name", "message": "Last name must be at most 50 characters"}],
        )

    normalized_username = validate_username(username)
    normalized_email = email.strip().lower()
    validated_password = validate_password(password)
    hashed_password = hash_password(validated_password)

    existing_email = await auth_service.get_user_by_email(db, normalized_email)
    if existing_email is not None:
        raise AppException(
            code="EMAIL_ALREADY_IN_USE",
            message="This email is already in use by another account",
            status_code=409,
            details=[
                {
                    "field": "email",
                    "message": "This email is already in use by another account",
                }
            ],
        )

    existing_username = await get_user_by_username(db, normalized_username)
    if existing_username is not None:
        raise AppException(
            code="USERNAME_ALREADY_IN_USE",
            message="This username is already in use by another account",
            status_code=409,
            details=[
                {
                    "field": "username",
                    "message": "This username is already in use by another account",
                }
            ],
        )

    now = _utcnow()
    otp_code = generate_otp_code()
    selected_role = await role_selection_service.resolve_registration_role(db, session_token)
    user = User(
        first_name=normalized_first_name,
        last_name=normalized_last_name,
        username=normalized_username,
        email=normalized_email,
        phone=phone.strip() if phone and phone.strip() else None,
        encrypted_password=hashed_password,
        role=selected_role,
        org_id=None,
        is_super_admin=False,
        is_active=True,
        email_confirmed_at=None,
        confirmation_token=hash_otp(otp_code),
        confirmation_sent_at=now,
        terms_accepted_at=now,
    )
    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.warning(
            "Integrity error registering coach email=%s username=%s",
            normalized_email,
            normalized_username,
        )
        email_conflict = await auth_service.get_user_by_email(db, normalized_email)
        if email_conflict is not None:
            raise AppException(
                code="EMAIL_ALREADY_IN_USE",
                message="This email is already in use by another account",
                status_code=409,
                details=[
                    {
                        "field": "email",
                        "message": "This email is already in use by another account",
                    }
                ],
            ) from None
        raise AppException(
            code="USERNAME_ALREADY_IN_USE",
            message="This username is already in use by another account",
            status_code=409,
            details=[
                {
                    "field": "username",
                    "message": "This username is already in use by another account",
                }
            ],
        ) from None

    await db.refresh(user)

    try:
        send_verification_email(user.email, otp_code)
    except Exception:
        logger.exception("Failed to send verification email to %s", user.email)

    access_token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role},
    )
    logger.info("Registered coach user %s username=%s", user.id, user.username)

    return RegisterResult(
        user=user,
        access_token=access_token,
        expires_in_hours=settings.ACCESS_TOKEN_EXPIRE_HOURS,
    )


def build_register_user_name(user: User) -> str:
    """Build the display name included in registration responses."""
    return display_name(user)
