import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import send_password_reset_email
from app.core.security import (
    create_access_token,
    decode_token,
    generate_reset_token,
    get_token_id,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.models.enums import UserRole
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.auth import (
    CoachLoginResponse,
    CoachUserPublic,
    LoginResponse,
    UserPublic,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_usable(user: User) -> bool:
    if not user.is_active or user.deleted_at is not None:
        return False
    if user.banned_until is not None and user.banned_until > _utcnow():
        return False
    return True


async def is_token_revoked(db: AsyncSession, token: str, payload: dict | None = None) -> bool:
    token_id = get_token_id(token, payload)
    result = await db.execute(
        select(RevokedToken.id).where(RevokedToken.token_id == token_id)
    )
    return result.scalar_one_or_none() is not None


async def logout_user(db: AsyncSession, token: str, user_id: UUID) -> None:
    payload = decode_token(token)
    token_id = get_token_id(token, payload)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    existing = await db.execute(
        select(RevokedToken.id).where(RevokedToken.token_id == token_id)
    )
    if existing.scalar_one_or_none() is None:
        db.add(
            RevokedToken(
                token_id=token_id,
                user_id=user_id,
                expires_at=expires_at,
            )
        )
        await db.commit()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(
            User.email == email.strip().lower(),
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """Look up a non-deleted user by username."""
    result = await db.execute(
        select(User).where(
            User.username == username.strip(),
            User.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_coach_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    """Resolve a coach account by email address or username."""
    cleaned = identifier.strip()
    if not cleaned:
        return None

    if "@" in cleaned:
        user = await get_user_by_email(db, cleaned)
    else:
        user = await get_user_by_username(db, cleaned)

    if user is None or user.role != UserRole.COACH.value:
        return None
    return user


def _coach_can_login(user: User) -> bool:
    """Return True when the coach account may authenticate."""
    if not _is_usable(user):
        return False
    if user.email_confirmed_at is None:
        return False
    return True


async def login_coach(
    db: AsyncSession,
    identifier: str,
    password: str,
    *,
    remember_me: bool = False,
) -> CoachLoginResponse | None:
    """
    Authenticate a verified coach by email or username and password.

    Returns None when credentials are invalid, the account is inactive, or
    email verification is pending.
    """
    user = await get_coach_by_identifier(db, identifier)
    if user is None or not _coach_can_login(user):
        return None
    if not verify_password(password, user.encrypted_password):
        return None

    expires_in_hours = (
        settings.REMEMBER_ME_TOKEN_EXPIRE_HOURS
        if remember_me
        else settings.ACCESS_TOKEN_EXPIRE_HOURS
    )

    user.last_sign_in_at = _utcnow()
    await db.commit()
    await db.refresh(user)

    token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role},
        expire_hours=expires_in_hours,
    )
    return CoachLoginResponse(
        message="Login successful",
        description="Welcome back to Hoops Engine",
        link=f"{settings.FRONTEND_URL.rstrip('/')}/coach/dashboard",
        access_token=token,
        expires_in_hours=expires_in_hours,
        remember_me=remember_me,
        user=CoachUserPublic.model_validate(user),
    )


async def request_coach_password_reset(db: AsyncSession, email: str) -> str | None:
    """Initiate password recovery for an active coach account."""
    user = await get_user_by_email(db, email)
    if user is None or not _is_usable(user) or user.role != UserRole.COACH.value:
        return None
    return await request_password_reset(db, email)


async def login_user(db: AsyncSession, email: str, password: str) -> LoginResponse | None:
    user = await get_user_by_email(db, email)
    if user is None or not _is_usable(user):
        return None
    if not verify_password(password, user.encrypted_password):
        return None

    user.last_sign_in_at = _utcnow()
    await db.commit()
    await db.refresh(user)

    token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role},
    )
    return LoginResponse(
        access_token=token,
        expires_in_hours=settings.ACCESS_TOKEN_EXPIRE_HOURS,
        user=UserPublic.model_validate(user),
    )


async def request_password_reset(db: AsyncSession, email: str) -> str | None:
    user = await get_user_by_email(db, email)
    if user is None or not _is_usable(user):
        return None

    raw_token = generate_reset_token()
    user.recovery_token = hash_reset_token(raw_token)
    user.recovery_sent_at = _utcnow()
    await db.commit()

    try:
        send_password_reset_email(user.email, raw_token)
    except Exception:
        logger.exception("Failed to send password reset email to %s", user.email)

    return raw_token


async def validate_reset_token(db: AsyncSession, token: str) -> User | None:
    token_hash = hash_reset_token(token)
    result = await db.execute(select(User).where(User.recovery_token == token_hash))
    user = result.scalar_one_or_none()
    if user is None or not _is_usable(user) or user.recovery_sent_at is None:
        return None

    sent_at = user.recovery_sent_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    expires_at = sent_at + timedelta(hours=settings.RESET_TOKEN_EXPIRE_HOURS)
    if _utcnow() > expires_at:
        return None

    return user


async def reset_password(db: AsyncSession, token: str, new_password: str) -> bool:
    user = await validate_reset_token(db, token)
    if user is None:
        return False

    user.encrypted_password = hash_password(new_password)
    user.recovery_token = None
    user.recovery_sent_at = None
    user.updated_at = _utcnow()
    await db.commit()
    return True
