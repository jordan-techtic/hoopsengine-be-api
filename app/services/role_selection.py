"""Business logic for pre-registration role selection."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.role_selection import RoleSelection
from app.schemas.user import RoleOption, normalize_role_value

logger = logging.getLogger(__name__)

ROLE_SELECTION_OPTIONS: tuple[RoleOption, ...] = (
    RoleOption(
        value=UserRole.COACH.value,
        label="Coach",
        description="Manage teams, practices, and player development",
    ),
    RoleOption(
        value=UserRole.PLAYER.value,
        label="Player",
        description="Track your training progress and performance",
    ),
    RoleOption(
        value=UserRole.ORG_ADMIN.value,
        label="Organiser",
        description="Administer your organization and coaching staff",
    ),
)

ALLOWED_SELECTION_VALUES = frozenset(option.value for option in ROLE_SELECTION_OPTIONS)

# Roles that are recognized system-wide but not offered on this screen.
DISALLOWED_ON_SCREEN = frozenset({UserRole.SUPER_ADMIN.value})

# Completely undefined role labels that should return 400 (per acceptance criteria).
UNDEFINED_ROLE_EXAMPLES = frozenset({"referee"})


def _registration_link() -> str:
    """Return the frontend URL for the registration step after role selection."""
    return f"{settings.FRONTEND_URL.rstrip('/')}/register"


def list_available_roles() -> list[RoleOption]:
    """Return the static catalog of roles shown on the Role Selection screen."""
    return list(ROLE_SELECTION_OPTIONS)


def normalize_selection_role(raw_value: str) -> str:
    """
    Validate and normalize a role selection from UI labels or stored values.

    Raises AppException 400 when empty or undefined (e.g. Referee).
    Raises AppException 409 when the role is valid system-wide but not selectable here.
    """
    cleaned = (raw_value or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="A role must be selected before continuing",
            status_code=400,
            details=[
                {
                    "field": "selected_role",
                    "message": "A role must be selected before continuing",
                }
            ],
        )

    normalized_key = cleaned.lower().replace(" ", "_")
    if normalized_key in UNDEFINED_ROLE_EXAMPLES:
        raise AppException(
            code="VALIDATION_ERROR",
            message="The selected role is not defined",
            status_code=400,
            details=[
                {
                    "field": "selected_role",
                    "message": "The selected role is not defined",
                }
            ],
        )

    try:
        role = normalize_role_value(cleaned)
    except ValueError as exc:
        raise AppException(
            code="ROLE_NOT_ALLOWED",
            message="The selected role is not available for registration",
            status_code=409,
            details=[
                {
                    "field": "selected_role",
                    "message": "The selected role is not available for registration",
                }
            ],
        ) from exc

    role_value = role.value
    if role_value in DISALLOWED_ON_SCREEN:
        raise AppException(
            code="ROLE_NOT_ALLOWED",
            message="The selected role is not available for registration",
            status_code=409,
            details=[
                {
                    "field": "selected_role",
                    "message": "The selected role is not available for registration",
                }
            ],
        )

    if role_value not in ALLOWED_SELECTION_VALUES:
        raise AppException(
            code="ROLE_NOT_ALLOWED",
            message="The selected role is not available for registration",
            status_code=409,
            details=[
                {
                    "field": "selected_role",
                    "message": "The selected role is not available for registration",
                }
            ],
        )

    return role_value


def _selection_to_response(row: RoleSelection, *, message: str) -> dict[str, Any]:
    """Map a RoleSelection ORM row to the mobile API envelope."""
    return {
        "success": True,
        "message": message,
        "status": "ready",
        "description": "Continue to registration to create your account",
        "title": "Select Your Role",
        "link": _registration_link(),
        "error": None,
        "session_token": row.session_token,
        "selected_role": row.selected_role,
        "role": row.selected_role,
        "id": row.id,
    }


async def get_role_selection_by_token(
    db: AsyncSession,
    session_token: UUID,
) -> RoleSelection | None:
    """Load a role selection row by its public session token."""
    result = await db.execute(
        select(RoleSelection).where(RoleSelection.session_token == session_token)
    )
    return result.scalar_one_or_none()


async def submit_role_selection(
    db: AsyncSession,
    *,
    selected_role: str,
    session_token: UUID | None = None,
) -> dict[str, Any]:
    """
    Persist a role selection and return the API response envelope.

    Creates a new session when session_token is omitted; updates an existing row otherwise.
    """
    role_value = normalize_selection_role(selected_role)

    if session_token is not None:
        existing = await get_role_selection_by_token(db, session_token)
        if existing is None:
            raise AppException(
                code="ROLE_SELECTION_NOT_FOUND",
                message="Role selection session not found",
                status_code=404,
                details=[
                    {
                        "field": "session_token",
                        "message": "Role selection session not found",
                    }
                ],
            )
        if existing.selected_role == role_value:
            raise AppException(
                code="ROLE_SELECTION_UNCHANGED",
                message="Role selection has already been saved with this role",
                status_code=409,
                details=[
                    {
                        "field": "selected_role",
                        "message": "Role selection has already been saved with this role",
                    }
                ],
            )
        existing.selected_role = role_value
        await db.commit()
        await db.refresh(existing)
        logger.info(
            "Updated role selection session %s to role=%s",
            existing.session_token,
            role_value,
        )
        return _selection_to_response(existing, message="Role selected successfully")

    new_token = uuid.uuid4()
    row = RoleSelection(session_token=new_token, selected_role=role_value)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info("Created role selection session %s role=%s", new_token, role_value)
    return _selection_to_response(row, message="Role selected successfully")


async def get_current_selection(
    db: AsyncSession,
    session_token: UUID,
) -> dict[str, Any]:
    """Return the current role selection for a session token."""
    row = await get_role_selection_by_token(db, session_token)
    if row is None:
        raise AppException(
            code="ROLE_SELECTION_NOT_FOUND",
            message="Role selection session not found",
            status_code=404,
            details=[
                {
                    "field": "session_token",
                    "message": "Role selection session not found",
                }
            ],
        )
    return _selection_to_response(row, message="Role selection loaded")


def build_roles_catalog_response() -> dict[str, Any]:
    """Build the GET /role-selection/roles response envelope."""
    roles = list_available_roles()
    return {
        "success": True,
        "message": "Roles loaded successfully" if roles else "No roles are available",
        "status": "ready" if roles else "empty",
        "description": "Choose how you will use Hoops Engine",
        "title": "Select Your Role",
        "link": None,
        "error": None,
        # Mobile envelope placeholders until the user selects a role / registers.
        "id": None,
        "role": None,
        "image": None,
        "phone": None,
        "phone_number": None,
        "email": None,
        "name": None,
        "first_name": None,
        "last_name": None,
        "address": None,
        "roles": [role.model_dump() for role in roles],
    }


async def resolve_registration_role(
    db: AsyncSession,
    session_token: UUID | None,
) -> str:
    """
    Return the role to assign during registration from a prior selection session.

    Defaults to coach when no token is supplied or the session is missing.
    """
    if session_token is None:
        return UserRole.COACH.value

    row = await get_role_selection_by_token(db, session_token)
    if row is None:
        return UserRole.COACH.value

    return row.selected_role
