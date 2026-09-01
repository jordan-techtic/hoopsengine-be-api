"""Business logic for organization admin coach management."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.org_admin_coach import (
    COACH_REMOVAL_CONFIRMATION_MESSAGE,
    OrgAdminCoachRemovalRequest,
    OrgAdminCoachUpdateRequest,
)
from app.services import client_db
from app.services.account_settings import split_full_name
from app.services.org_admin_profile import require_admin_organization
from app.services.organization import validate_phone_number
from app.services.profile import validate_profile_email

logger = logging.getLogger(__name__)

COACHES_TABLE = "coaches"
TEAMS_TABLE = "teams"


def _require_non_empty(value: str, field: str, label: str | None = None) -> str:
    """Return trimmed text or raise 400 when a required field is empty."""
    cleaned = value.strip()
    if not cleaned:
        display = label or field.replace("_", " ").title()
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{display} is required",
            status_code=400,
            details=[{"field": field, "message": f"{display} is required"}],
        )
    return cleaned


def _validate_coach_phone(phone: str) -> str:
    """Validate coach phone and map validation errors to the Figma `phone` field."""
    try:
        return validate_phone_number(phone)
    except AppException as exc:
        if exc.code != "VALIDATION_ERROR":
            raise
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid phone number",
            status_code=400,
            details=[{"field": "phone", "message": "Enter a valid phone number"}],
        ) from exc


async def _require_coaches_table(db: AsyncSession) -> None:
    """Raise 503 when the client-domain coaches table is unavailable."""
    if not await client_db.table_exists(db, COACHES_TABLE):
        raise AppException(
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Coach operations are temporarily unavailable",
            status_code=503,
        )


async def _fetch_coach_row(
    db: AsyncSession,
    *,
    coach_id: UUID,
    org_id: UUID,
) -> dict[str, Any] | None:
    """Load a coach row scoped to the organization."""
    result = await db.execute(
        text(
            f"""
            SELECT
                c.id,
                c.org_id,
                c.first_name,
                c.last_name,
                c.email,
                c.team_id,
                t.name AS team_name
            FROM {COACHES_TABLE} c
            LEFT JOIN {TEAMS_TABLE} t
              ON t.id = c.team_id
             AND t.org_id = c.org_id
            WHERE c.id = :coach_id
              AND c.org_id = :org_id
            LIMIT 1
            """
        ),
        {"coach_id": coach_id, "org_id": org_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _fetch_linked_coach_user(
    db: AsyncSession,
    *,
    org_id: UUID,
    email: str | None,
) -> User | None:
    """Return the coach user account linked by email within the organization."""
    cleaned = (email or "").strip()
    if not cleaned:
        return None

    result = await db.execute(
        select(User).where(
            User.org_id == org_id,
            User.role == UserRole.COACH.value,
            User.email.ilike(cleaned),
        )
    )
    return result.scalar_one_or_none()


async def _email_in_use_by_other_user(
    db: AsyncSession,
    *,
    email: str,
    exclude_user_id: UUID | None = None,
) -> bool:
    """Return True when another user account already owns the email."""
    query = select(User.id).where(User.email == email)
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


async def _email_in_use_by_other_coach(
    db: AsyncSession,
    *,
    org_id: UUID,
    email: str,
    exclude_coach_id: UUID,
) -> bool:
    """Return True when another coach in the organization already uses the email."""
    exists = await db.scalar(
        text(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM {COACHES_TABLE}
                WHERE org_id = :org_id
                  AND id <> :exclude_coach_id
                  AND email ILIKE :email
            )
            """
        ),
        {"org_id": org_id, "exclude_coach_id": exclude_coach_id, "email": email},
    )
    return bool(exists)


async def _resolve_team_id(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_assignment: str,
) -> UUID:
    """Resolve a team id from the selected team name within the organization."""
    cleaned = _require_non_empty(team_assignment, "team_assignment", "Team assignment")
    if not await client_db.table_exists(db, TEAMS_TABLE):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Selected team was not found in your organization",
            status_code=400,
            details=[
                {
                    "field": "team_assignment",
                    "message": "Selected team was not found in your organization",
                }
            ],
        )

    row = await db.execute(
        text(
            f"""
            SELECT id
            FROM {TEAMS_TABLE}
            WHERE org_id = :org_id
              AND name ILIKE :team_name
            LIMIT 1
            """
        ),
        {"org_id": org_id, "team_name": cleaned},
    )
    team_id = row.scalar_one_or_none()
    if team_id is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Selected team was not found in your organization",
            status_code=400,
            details=[
                {
                    "field": "team_assignment",
                    "message": "Selected team was not found in your organization",
                }
            ],
        )
    return UUID(str(team_id))


def _build_detail_payload(
    *,
    coach_row: dict[str, Any],
    organization_name: str,
    phone_value: str | None,
    message: str,
    status: str = "ready",
) -> dict[str, Any]:
    """Shape a coach detail envelope for org-admin edit responses."""
    first_name = str(coach_row.get("first_name") or "").strip()
    last_name = str(coach_row.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip() or "Coach"
    team_name = coach_row.get("team_name")

    return {
        "success": True,
        "message": message,
        "status": status,
        "description": "Coach profile and contact information",
        "link": None,
        "error": None,
        "id": coach_row["id"],
        "name": full_name,
        "full_name": full_name,
        "email": coach_row.get("email"),
        "phone_number": phone_value,
        "phone": phone_value,
        "team_assignment": team_name,
        "team": team_name,
        "coach_id": coach_row["id"],
        "confirmation_message": COACH_REMOVAL_CONFIRMATION_MESSAGE,
        "organization": organization_name,
    }


async def get_coach_detail(
    db: AsyncSession,
    user: User,
    coach_id: UUID,
) -> dict[str, Any]:
    """Return coach details scoped to the authenticated org admin's organization."""
    organization = await require_admin_organization(db, user)
    await _require_coaches_table(db)

    row = await _fetch_coach_row(db, coach_id=coach_id, org_id=organization.id)
    if row is None:
        raise AppException(
            code="COACH_NOT_FOUND",
            message="Coach not found",
            status_code=404,
            details=[{"field": "coach_id", "message": "Coach not found"}],
        )

    linked_user = await _fetch_linked_coach_user(db, org_id=organization.id, email=row.get("email"))
    phone_value = linked_user.phone if linked_user is not None else None

    logger.info("Org admin %s loaded coach %s", user.id, coach_id)
    return _build_detail_payload(
        coach_row=row,
        organization_name=organization.name,
        phone_value=phone_value,
        message="Coach details loaded successfully",
    )


async def update_coach(
    db: AsyncSession,
    user: User,
    coach_id: UUID,
    payload: OrgAdminCoachUpdateRequest,
) -> dict[str, Any]:
    """Update a coach record scoped to the authenticated org admin's organization."""
    organization = await require_admin_organization(db, user)
    await _require_coaches_table(db)

    row = await _fetch_coach_row(db, coach_id=coach_id, org_id=organization.id)
    if row is None:
        raise AppException(
            code="COACH_NOT_FOUND",
            message="Coach not found",
            status_code=404,
            details=[{"field": "coach_id", "message": "Coach not found"}],
        )

    full_name = _require_non_empty(payload.full_name, "full_name", "Full name")
    first_name, last_name = split_full_name(full_name)
    if not first_name:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Full name is required",
            status_code=400,
            details=[{"field": "full_name", "message": "Full name is required"}],
        )

    normalized_email = validate_profile_email(_require_non_empty(payload.email, "email", "Email"))
    phone_raw = _require_non_empty(payload.phone, "phone", "Phone")
    normalized_phone = _validate_coach_phone(phone_raw)

    linked_user = await _fetch_linked_coach_user(
        db,
        org_id=organization.id,
        email=row.get("email"),
    )

    if await _email_in_use_by_other_coach(
        db,
        org_id=organization.id,
        email=normalized_email,
        exclude_coach_id=coach_id,
    ):
        raise AppException(
            code="EMAIL_ALREADY_IN_USE",
            message="This email is already in use by another coach",
            status_code=409,
            details=[
                {
                    "field": "email",
                    "message": "This email is already in use by another coach",
                }
            ],
        )

    exclude_user_id = linked_user.id if linked_user is not None else None
    if await _email_in_use_by_other_user(
        db,
        email=normalized_email,
        exclude_user_id=exclude_user_id,
    ):
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

    updates: dict[str, Any] = {
        "first_name": first_name,
        "last_name": last_name or first_name,
        "email": normalized_email,
    }

    if payload.team_assignment is not None:
        updates["team_id"] = await _resolve_team_id(
            db,
            org_id=organization.id,
            team_assignment=payload.team_assignment,
        )

    set_clauses = ", ".join(f"{column} = :{column}" for column in updates)
    await db.execute(
        text(
            f"""
            UPDATE {COACHES_TABLE}
            SET {set_clauses}
            WHERE id = :coach_id
              AND org_id = :org_id
            """
        ),
        {"coach_id": coach_id, "org_id": organization.id, **updates},
    )

    if linked_user is not None:
        linked_user.first_name = first_name
        linked_user.last_name = last_name or first_name
        linked_user.email = normalized_email
        linked_user.phone = normalized_phone
        await db.commit()
        await db.refresh(linked_user)
    else:
        await db.commit()

    updated_row = await _fetch_coach_row(db, coach_id=coach_id, org_id=organization.id)
    if updated_row is None:
        raise AppException(
            code="COACH_NOT_FOUND",
            message="Coach not found",
            status_code=404,
            details=[{"field": "coach_id", "message": "Coach not found"}],
        )

    refreshed_user = await _fetch_linked_coach_user(
        db,
        org_id=organization.id,
        email=updated_row.get("email"),
    )
    phone_value = refreshed_user.phone if refreshed_user is not None else normalized_phone

    logger.info("Org admin %s updated coach %s", user.id, coach_id)
    return _build_detail_payload(
        coach_row=updated_row,
        organization_name=organization.name,
        phone_value=phone_value,
        message="Coach updated successfully",
        status="updated",
    )


async def remove_coach(
    db: AsyncSession,
    user: User,
    coach_id: UUID,
    payload: OrgAdminCoachRemovalRequest | None = None,
) -> None:
    """Remove a coach from the authenticated org admin's organization."""
    organization = await require_admin_organization(db, user)
    await _require_coaches_table(db)

    if payload is not None and payload.phone is not None and payload.phone.strip():
        _validate_coach_phone(payload.phone.strip())

    row = await _fetch_coach_row(db, coach_id=coach_id, org_id=organization.id)
    if row is None:
        raise AppException(
            code="COACH_NOT_FOUND",
            message="Coach not found",
            status_code=404,
            details=[{"field": "coach_id", "message": "Coach not found"}],
        )

    result = await db.execute(
        text(
            f"""
            DELETE FROM {COACHES_TABLE}
            WHERE id = :coach_id
              AND org_id = :org_id
            """
        ),
        {"coach_id": coach_id, "org_id": organization.id},
    )
    if result.rowcount == 0:
        raise AppException(
            code="COACH_NOT_FOUND",
            message="Coach not found",
            status_code=404,
            details=[{"field": "coach_id", "message": "Coach not found"}],
        )

    await db.commit()
    logger.info("Org admin %s removed coach %s", user.id, coach_id)
