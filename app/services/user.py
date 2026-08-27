import logging
import math
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.core.security import BCRYPT_MAX_PASSWORD_BYTES, hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import AdminUserItem, AdminUserMutationResponse, RoleOption
from app.services import auth as auth_service
from app.services import organization as organization_service

logger = logging.getLogger(__name__)

PASSWORD_SPECIAL = re.compile(r"[^A-Za-z0-9]")

ROLE_OPTIONS: tuple[RoleOption, ...] = (
    RoleOption(value=UserRole.COACH.value, label="Coach", description="Coach account"),
    RoleOption(value=UserRole.PLAYER.value, label="Player", description="Player account"),
    RoleOption(
        value=UserRole.ORG_ADMIN.value,
        label="Organization Admin",
        description="Organization administrator",
    ),
    RoleOption(
        value=UserRole.SUPER_ADMIN.value,
        label="Super Admin",
        description="Platform super administrator",
    ),
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def display_name(user: User) -> str:
    """Build a UI display name from first and last name."""
    parts = [user.first_name, user.last_name]
    name = " ".join(part.strip() for part in parts if part and part.strip())
    return name or user.email


def split_display_name(name: str) -> tuple[str, str]:
    """Split a full name into first and last name."""
    cleaned = name.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Name is required",
            status_code=400,
            details=[{"field": "name", "message": "Name is required"}],
        )
    parts = cleaned.split(None, 1)
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], parts[1]


def validate_password(password: str) -> str:
    """Enforce project password complexity rules. Raises 400 when invalid."""
    if len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password is too long",
            status_code=400,
            details=[{"field": "password", "message": "Password is too long"}],
        )
    if len(password) < 8:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password must be at least 8 characters",
            status_code=400,
            details=[{"field": "password", "message": "Password must be at least 8 characters"}],
        )
    if not re.search(r"[A-Z]", password):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password must include at least one uppercase letter",
            status_code=400,
            details=[{"field": "password", "message": "Password must include at least one uppercase letter"}],
        )
    if not re.search(r"[a-z]", password):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password must include at least one lowercase letter",
            status_code=400,
            details=[{"field": "password", "message": "Password must include at least one lowercase letter"}],
        )
    if not re.search(r"[0-9]", password):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password must include at least one number",
            status_code=400,
            details=[{"field": "password", "message": "Password must include at least one number"}],
        )
    if not PASSWORD_SPECIAL.search(password):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Password must include at least one special character",
            status_code=400,
            details=[{"field": "password", "message": "Password must include at least one special character"}],
        )
    return password


def analyze_password_strength(password: str) -> dict[str, bool]:
    """Return password requirement checklist without raising validation errors."""
    return {
        "min_length": len(password) >= 8,
        "has_uppercase": bool(re.search(r"[A-Z]", password)),
        "has_lowercase": bool(re.search(r"[a-z]", password)),
        "has_number": bool(re.search(r"[0-9]", password)),
        "has_special": bool(PASSWORD_SPECIAL.search(password)),
    }


def is_password_strong(password: str) -> bool:
    """Return True when the password satisfies all complexity rules."""
    if len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    checks = analyze_password_strength(password)
    return all(checks.values())


def assignable_roles() -> list[RoleOption]:
    """Return roles for the Manage Users Add/Edit dropdown."""
    return list(ROLE_OPTIONS)


def to_item(user: User, *, current_user_id: UUID | None = None) -> AdminUserItem:
    """Map a User ORM row to the admin API item schema. Never includes password."""
    role = UserRole(user.role)
    return AdminUserItem(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        name=display_name(user),
        email=user.email,
        role=role,
        roles=[role.value],
        description=None,
        org_id=user.org_id,
        is_super_admin=user.is_super_admin,
        is_active=user.is_active,
        is_self=current_user_id is not None and user.id == current_user_id,
        last_sign_in_at=user.last_sign_in_at,
        created_at=user.created_at,
    )


def to_mutation_response(
    user: User,
    message: str,
    *,
    current_user_id: UUID | None = None,
) -> AdminUserMutationResponse:
    """Map a User ORM row to a create/update response with a toast message."""
    item = to_item(user, current_user_id=current_user_id)
    return AdminUserMutationResponse(message=message, **item.model_dump())


def build_pagination_meta(total: int, page: int, page_size: int) -> dict[str, int | bool]:
    """Build list pagination metadata matching other admin list endpoints."""
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1 and total_pages > 0,
    }


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """Return a non-deleted user by id, or None."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def _require_organization(db: AsyncSession, org_id: UUID) -> None:
    organization = await organization_service.get_organization_by_id(db, org_id)
    if organization is None:
        raise AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization not found",
            status_code=400,
            details=[{"field": "org_id", "message": "Organization not found"}],
        )


async def list_users(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    role: UserRole | None = None,
    search: str | None = None,
) -> tuple[list[User], int]:
    """Return a page of non-deleted users ordered by newest first."""
    filters = [User.deleted_at.is_(None)]
    if role is not None:
        filters.append(User.role == role.value)
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                User.email.ilike(term),
                User.first_name.ilike(term),
                User.last_name.ilike(term),
            )
        )

    count_stmt = select(func.count()).select_from(User).where(*filters)
    list_stmt = (
        select(User)
        .where(*filters)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    total = int(await db.scalar(count_stmt) or 0)
    result = await db.execute(list_stmt)
    return list(result.scalars().all()), total


async def create_user(
    db: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    role: UserRole,
    org_id: UUID | None = None,
) -> User:
    """Create a user account. Raises 409 when the email is already in use."""
    hashed_password = hash_password(validate_password(password))
    normalized_email = email.strip().lower()
    existing = await auth_service.get_user_by_email(db, normalized_email)
    if existing is not None:
        raise AppException(
            code="EMAIL_ALREADY_IN_USE",
            message="This email is already in use by another account",
            status_code=409,
            details=[{"field": "email", "message": "This email is already in use by another account"}],
        )

    if org_id is not None:
        await _require_organization(db, org_id)

    now = _utcnow()
    user = User(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=normalized_email,
        encrypted_password=hashed_password,
        role=role.value,
        org_id=org_id,
        is_super_admin=role == UserRole.SUPER_ADMIN,
        is_active=True,
        email_confirmed_at=now,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.warning("Integrity error creating user email=%s", normalized_email)
        raise AppException(
            code="EMAIL_ALREADY_IN_USE",
            message="This email is already in use by another account",
            status_code=409,
            details=[{"field": "email", "message": "This email is already in use by another account"}],
        ) from None
    await db.refresh(user)
    logger.info("Created user %s role=%s", user.id, user.role)
    return user


async def update_user(
    db: AsyncSession,
    user_id: UUID,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    name: str | None = None,
    email: str | None = None,
    password: str | None = None,
    role: UserRole | None = None,
    org_id: UUID | None = None,
    org_id_set: bool = False,
) -> User:
    """Update a non-deleted user. Raises 404 if missing, 409 on duplicate email."""
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="User not found",
            status_code=404,
        )

    if name is not None and first_name is None and last_name is None:
        first_name, last_name = split_display_name(name)

    if first_name is not None:
        user.first_name = first_name.strip()
    if last_name is not None:
        user.last_name = last_name.strip()

    if email is not None:
        normalized_email = email.strip().lower()
        existing = await auth_service.get_user_by_email(db, normalized_email)
        if existing is not None and existing.id != user.id:
            raise AppException(
                code="EMAIL_ALREADY_IN_USE",
                message="This email is already in use by another account",
                status_code=409,
                details=[{"field": "email", "message": "This email is already in use by another account"}],
            )
        user.email = normalized_email

    if password is not None:
        user.encrypted_password = hash_password(validate_password(password))

    if role is not None:
        user.role = role.value
        user.is_super_admin = role == UserRole.SUPER_ADMIN

    if org_id_set:
        if org_id is not None:
            await _require_organization(db, org_id)
        user.org_id = org_id

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppException(
            code="EMAIL_ALREADY_IN_USE",
            message="This email is already in use by another account",
            status_code=409,
            details=[{"field": "email", "message": "This email is already in use by another account"}],
        ) from None
    await db.refresh(user)
    logger.info("Updated user %s", user.id)
    return user


async def delete_user(
    db: AsyncSession,
    user_id: UUID,
    *,
    current_user_id: UUID,
) -> None:
    """Soft-delete a user. Cannot remove the authenticated super admin's own account."""
    if user_id == current_user_id:
        raise AppException(
            code="CANNOT_DELETE_SELF",
            message="You cannot remove your own account",
            status_code=400,
        )

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise AppException(
            code="USER_NOT_FOUND",
            message="User not found",
            status_code=404,
        )

    user.deleted_at = _utcnow()
    user.is_active = False
    await db.commit()
    logger.info("Soft-deleted user %s", user_id)
