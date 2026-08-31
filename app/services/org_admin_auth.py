"""Organization Admin authentication service (HE-423)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.security import create_access_token, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.org_admin_auth import OrgAdminLoginResponse, OrgAdminUserPublic
from app.services import auth as auth_service
from app.services.organization import get_organization_by_id
from app.services.registration import USERNAME_PATTERN

logger = logging.getLogger(__name__)

_email_adapter = TypeAdapter(EmailStr)

LOGIN_SUCCESS_MESSAGE = "Login successful! Redirecting to dashboard..."
INVALID_CREDENTIALS_MESSAGE = "Invalid username or password. Please try again."


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dashboard_link() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/organization/dashboard"


def resolve_login_identifier(*, email: str | None, username: str | None) -> str:
    """Return the login identifier from email or username fields."""
    for candidate in (email, username):
        if candidate is not None and candidate.strip():
            return candidate.strip()
    raise AppException(
        code="VALIDATION_ERROR",
        message="Username is required",
        status_code=400,
        details=[{"field": "username", "message": "Username is required"}],
    )


def validate_login_identifier_format(identifier: str) -> None:
    """Raise 400 when the login identifier format is invalid."""
    cleaned = identifier.strip()
    if USERNAME_PATTERN.match(cleaned):
        return

    try:
        _email_adapter.validate_python(cleaned.lower())
    except ValidationError as exc:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid email address",
            status_code=400,
            details=[{"field": "email", "message": "Enter a valid email address"}],
        ) from exc


def validate_login_password(password: str | None) -> str:
    """Raise 400 when password is missing or clearly invalid for submission."""
    if password is None or not password.strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password is required",
            status_code=400,
            details=[{"field": "password", "message": "Password is required"}],
        )
    cleaned = password.strip()
    if len(cleaned) < 8:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password must be at least 8 characters",
            status_code=400,
            details=[
                {
                    "field": "password",
                    "message": "Password must be at least 8 characters",
                }
            ],
        )
    return cleaned


async def get_org_admin_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    """Resolve an organization admin account by email address or username."""
    cleaned = identifier.strip()
    if not cleaned:
        return None

    if "@" in cleaned:
        user = await auth_service.get_user_by_email(db, cleaned)
    else:
        user = await auth_service.get_user_by_username(db, cleaned)

    if user is None or user.role != UserRole.ORG_ADMIN.value:
        return None
    return user


def _org_admin_can_login(user: User) -> bool:
    """Return True when the organization admin account may authenticate."""
    if not user.is_active or user.deleted_at is not None:
        return False
    if user.banned_until is not None and user.banned_until > _utcnow():
        return False
    if user.email_confirmed_at is None:
        return False
    return True


async def login_org_admin(
    db: AsyncSession,
    *,
    email: str | None,
    username: str | None,
    password: str,
    remember_me: bool = False,
) -> OrgAdminLoginResponse | None:
    """
    Authenticate an organization admin by email/username and password.

    Returns None when credentials are invalid or the account cannot sign in.
    """
    identifier = resolve_login_identifier(email=email, username=username)
    validate_login_identifier_format(identifier)
    normalized_password = validate_login_password(password)

    user = await get_org_admin_by_identifier(db, identifier)
    if user is None or not _org_admin_can_login(user):
        return None
    if not verify_password(normalized_password, user.encrypted_password):
        return None

    expires_in_hours = (
        settings.REMEMBER_ME_TOKEN_EXPIRE_HOURS
        if remember_me
        else settings.ACCESS_TOKEN_EXPIRE_HOURS
    )

    user.last_sign_in_at = _utcnow()
    await db.commit()
    await db.refresh(user)

    organization_name: str | None = None
    if user.org_id is not None:
        organization = await get_organization_by_id(db, user.org_id)
        if organization is not None:
            organization_name = organization.name

    token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "role": user.role},
        expire_hours=expires_in_hours,
    )

    logger.info("Organization admin %s logged in", user.id)

    return OrgAdminLoginResponse(
        message=LOGIN_SUCCESS_MESSAGE,
        description="Welcome back to Hoops Engine",
        link=_dashboard_link(),
        id=user.id,
        email=user.email,
        username=user.username,
        organization=organization_name,
        access_token=token,
        expires_in_hours=expires_in_hours,
        remember_me=remember_me,
        user=OrgAdminUserPublic.model_validate(user),
    )
