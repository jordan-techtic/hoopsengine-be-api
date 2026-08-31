from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.security import decode_token
from app.models.enums import UserRole
from app.models.user import User
from app.services import auth as auth_service

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException(
            code="MISSING_TOKEN",
            message="Could not validate credentials",
            status_code=401,
        )

    token = credentials.credentials

    try:
        payload = decode_token(token)
        subject = payload.get("sub")
        token_type = payload.get("type")
        if not subject or token_type != "access":
            raise AppException(
                code="INVALID_TOKEN",
                message="Could not validate credentials",
                status_code=401,
            )
        user_id = UUID(str(subject))
    except (jwt.PyJWTError, ValueError):
        raise AppException(
            code="INVALID_TOKEN",
            message="Could not validate credentials",
            status_code=401,
        ) from None

    if await auth_service.is_token_revoked(db, token, payload):
        raise AppException(
            code="TOKEN_REVOKED",
            message="Session has expired or been logged out",
            status_code=401,
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppException(
            code="INVALID_TOKEN",
            message="Could not validate credentials",
            status_code=401,
        )
    return user


async def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Require a valid Bearer JWT for email verification endpoints.

    Returns 403 when credentials are missing, matching the verification API contract.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException(
            code="FORBIDDEN",
            message="Authentication is required to access this resource",
            status_code=403,
        )

    token = credentials.credentials

    try:
        payload = decode_token(token)
        subject = payload.get("sub")
        token_type = payload.get("type")
        if not subject or token_type != "access":
            raise AppException(
                code="FORBIDDEN",
                message="Authentication is required to access this resource",
                status_code=403,
            )
        user_id = UUID(str(subject))
    except (jwt.PyJWTError, ValueError):
        raise AppException(
            code="FORBIDDEN",
            message="Authentication is required to access this resource",
            status_code=403,
        ) from None

    if await auth_service.is_token_revoked(db, token, payload):
        raise AppException(
            code="FORBIDDEN",
            message="Authentication is required to access this resource",
            status_code=403,
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppException(
            code="FORBIDDEN",
            message="Authentication is required to access this resource",
            status_code=403,
        )
    return user


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppException(
            code="MISSING_TOKEN",
            message="Could not validate credentials",
            status_code=401,
        )
    return credentials.credentials


def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_super_admin:
        raise AppException(
            code="FORBIDDEN",
            message="You do not have permission to access this resource",
            status_code=403,
        )
    return current_user


def get_current_coach(current_user: User = Depends(get_current_user)) -> User:
    """Require an authenticated, email-verified coach account."""
    if current_user.role != UserRole.COACH.value:
        raise AppException(
            code="FORBIDDEN",
            message="You do not have permission to access this resource",
            status_code=403,
        )
    if current_user.email_confirmed_at is None:
        raise AppException(
            code="FORBIDDEN",
            message="Email verification is required to access this resource",
            status_code=403,
        )
    return current_user


def get_current_player(current_user: User = Depends(get_current_user)) -> User:
    """Require an authenticated player account."""
    if current_user.role != UserRole.PLAYER.value:
        raise AppException(
            code="FORBIDDEN",
            message="You do not have permission to access this resource",
            status_code=403,
        )
    return current_user
