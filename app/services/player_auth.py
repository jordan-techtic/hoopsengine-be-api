"""Player login and session validation service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import create_access_token, decode_token, verify_password
from app.models.enums import UserRole
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.player_auth import PlayerLoginResponse, PlayerUserPublic
from app.services import auth as auth_service
from app.services.registration import USERNAME_PATTERN

logger = logging.getLogger(__name__)

_email_adapter = TypeAdapter(EmailStr)

ACTIVE_SESSION_JTI_KEY = "active_session_jti"
ACTIVE_SESSION_EXP_KEY = "active_session_exp"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _player_dashboard_link() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/player/dashboard"


async def get_player_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    """Resolve a player account by email address or username."""
    cleaned = identifier.strip()
    if not cleaned:
        return None

    if "@" in cleaned:
        user = await auth_service.get_user_by_email(db, cleaned)
    else:
        user = await auth_service.get_user_by_username(db, cleaned)

    if user is None or user.role != UserRole.PLAYER.value:
        return None
    return user


def _player_can_login(user: User) -> bool:
    """Return True when the player account may authenticate."""
    if not user.is_active or user.deleted_at is not None:
        return False
    if user.banned_until is not None and user.banned_until > _utcnow():
        return False
    if user.email_confirmed_at is None:
        return False
    return True


def validate_identifier_format(identifier: str) -> list[dict[str, str]]:
    """Return field errors when the login identifier has an invalid email format."""
    return _validate_identifier_format(identifier)


def _validate_identifier_format(identifier: str) -> list[dict[str, str]]:
    """Return field errors when the login identifier has an invalid email format."""
    cleaned = identifier.strip()
    if USERNAME_PATTERN.match(cleaned):
        return []

    try:
        _email_adapter.validate_python(cleaned.lower())
    except ValidationError:
        return [{"field": "email", "message": "Enter a valid email address"}]
    return []


def validate_login_fields(*, email: str | None, password: str | None) -> dict[str, Any]:
    """
    Validate player login input for presence and email format.

    Returns a dict with ``valid``, ``message``, ``status``, ``title``, and optional
    ``errors`` suitable for PlayerLoginValidateResponse.
    """
    errors: list[dict[str, str]] = []

    if email is None or not email.strip():
        errors.append({"field": "email", "message": "Email or username is required"})
    else:
        errors.extend(_validate_identifier_format(email))

    if password is None or not password.strip():
        errors.append({"field": "password", "message": "Password is required"})

    if errors:
        return {
            "valid": False,
            "message": "Please fix the highlighted fields before signing in",
            "status": "invalid",
            "title": "LOGIN",
            "description": "Review the email/username and password fields",
            "errors": errors,
        }

    return {
        "valid": True,
        "message": "Login fields look good",
        "status": "valid",
        "title": "LOGIN",
        "description": "You can submit the login form",
        "errors": None,
    }


async def _has_active_session(db: AsyncSession, user: User) -> bool:
    """Return True when the player already has a non-revoked, unexpired session."""
    meta = user.raw_user_meta_data or {}
    jti = meta.get(ACTIVE_SESSION_JTI_KEY)
    exp_raw = meta.get(ACTIVE_SESSION_EXP_KEY)
    if not jti or not exp_raw:
        return False

    try:
        exp = datetime.fromisoformat(str(exp_raw))
    except ValueError:
        return False

    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if _utcnow() > exp:
        return False

    result = await db.execute(
        select(RevokedToken.id).where(RevokedToken.token_id == str(jti))
    )
    return result.scalar_one_or_none() is None


def _store_active_session(user: User, token: str) -> None:
    """Persist the active session identifier on the user metadata blob."""
    payload = decode_token(token)
    jti = payload.get("jti")
    exp_ts = payload.get("exp")
    if not jti or not exp_ts:
        return

    exp = datetime.fromtimestamp(int(exp_ts), tz=timezone.utc)
    meta = dict(user.raw_user_meta_data or {})
    meta[ACTIVE_SESSION_JTI_KEY] = str(jti)
    meta[ACTIVE_SESSION_EXP_KEY] = exp.isoformat()
    user.raw_user_meta_data = meta


async def login_player(
    db: AsyncSession,
    identifier: str,
    password: str,
    *,
    remember_me: bool = False,
) -> PlayerLoginResponse:
    """
    Authenticate a verified player by email or username and password.

    Raises AppException with 409 when an active session already exists.
    Returns None-equivalent failure by raising INVALID_CREDENTIALS via caller when
    credentials are invalid — caller should map to 401.
    """
    cleaned_identifier = identifier.strip()
    cleaned_password = password.strip()

    user = await get_player_by_identifier(db, cleaned_identifier)
    if user is None or not _player_can_login(user):
        raise AppException(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password",
            status_code=401,
        )

    if not verify_password(cleaned_password, user.encrypted_password):
        raise AppException(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password",
            status_code=401,
        )

    if await _has_active_session(db, user):
        raise AppException(
            code="DUPLICATE_SESSION",
            message="You are already signed in on this account",
            status_code=409,
            details=[
                {
                    "field": "email",
                    "message": "An active session already exists. Sign out before signing in again.",
                }
            ],
        )

    expires_in_hours = (
        settings.REMEMBER_ME_TOKEN_EXPIRE_HOURS
        if remember_me
        else settings.ACCESS_TOKEN_EXPIRE_HOURS
    )

    token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role},
        expire_hours=expires_in_hours,
    )

    user.last_sign_in_at = _utcnow()
    _store_active_session(user, token)
    await db.commit()
    await db.refresh(user)

    player_public = PlayerUserPublic.model_validate(user)
    logger.info("Player user %s signed in", user.id)

    return PlayerLoginResponse(
        message="Login successful",
        description="Welcome back to Hoops Engine",
        link=_player_dashboard_link(),
        email=user.email,
        username=user.username,
        id=user.id,
        access_token=token,
        expires_in_hours=expires_in_hours,
        remember_me=remember_me,
        user=player_public,
    )
