"""Business logic for organization admin coach invite and search."""

from __future__ import annotations

import logging
import secrets
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import send_coach_invite_email
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.org_admin_invite_coach import OrgAdminInviteCoachRequest
from app.services import client_db
from app.services.org_admin_profile import require_admin_organization
from app.services.profile import validate_profile_email

logger = logging.getLogger(__name__)

COACHES_TABLE = "coaches"
DEFAULT_COACH_ROLE = "subteam_coach"


def _require_non_empty_email(email: str) -> str:
    """Return trimmed email or raise 400 when empty."""
    cleaned = email.strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Email is required",
            status_code=400,
            details=[{"field": "email", "message": "Email is required"}],
        )
    return cleaned


def _build_invite_link(invite_token: str) -> str:
    """Build the frontend invitation URL for a coach invite token."""
    base_url = settings.FRONTEND_URL.rstrip("/")
    return f"{base_url}/coach/invite?token={invite_token}"


def _display_name_from_email(email: str) -> tuple[str, str]:
    """Derive placeholder first/last names from an email local part."""
    local_part = email.split("@", 1)[0].strip()
    if not local_part:
        return "Invited", "Coach"
    tokens = [part for part in local_part.replace(".", " ").replace("_", " ").split(" ") if part]
    if not tokens:
        return "Invited", "Coach"
    first_name = tokens[0].title()
    last_name = " ".join(token.title() for token in tokens[1:]) if len(tokens) > 1 else "Coach"
    return first_name, last_name


async def _require_coaches_table(db: AsyncSession) -> None:
    """Raise 503 when the client-domain coaches table is unavailable."""
    if not await client_db.table_exists(db, COACHES_TABLE):
        raise AppException(
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Coach invitation is temporarily unavailable",
            status_code=503,
        )


async def _column_exists(db: AsyncSession, column_name: str) -> bool:
    """Return True when a coaches-table column exists."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
            )
            """
        ),
        {"table_name": COACHES_TABLE, "column_name": column_name},
    )
    return bool(exists)


async def _email_in_use_by_user(db: AsyncSession, email: str) -> bool:
    """Return True when a user account already owns the email address."""
    result = await db.execute(select(User.id).where(User.email == email))
    return result.scalar_one_or_none() is not None


async def _email_in_use_by_org_coach(
    db: AsyncSession,
    *,
    org_id: UUID,
    email: str,
) -> bool:
    """Return True when a coach row in the organization already uses the email."""
    exists = await db.scalar(
        text(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM {COACHES_TABLE}
                WHERE org_id = :org_id
                  AND email ILIKE :email
            )
            """
        ),
        {"org_id": org_id, "email": email},
    )
    return bool(exists)


def _coach_status(row: dict[str, Any]) -> str:
    """Map a coach row to an Invite Coach screen status label."""
    invite_accepted = row.get("invite_accepted")
    if invite_accepted is True:
        return "active"
    if invite_accepted is False:
        return "invited"
    if row.get("invite_token"):
        return "invited"
    return "active"


def _coach_display_name(row: dict[str, Any]) -> str:
    """Return a display name for a coach row."""
    first_name = str(row.get("first_name") or "").strip()
    last_name = str(row.get("last_name") or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    return full_name or "Coach"


async def invite_coach(
    db: AsyncSession,
    user: User,
    payload: OrgAdminInviteCoachRequest,
) -> dict[str, Any]:
    """Invite a coach to the organization admin's organization by email."""
    organization = await require_admin_organization(db, user)
    await _require_coaches_table(db)

    normalized_email = validate_profile_email(_require_non_empty_email(payload.email))

    if await _email_in_use_by_org_coach(db, org_id=organization.id, email=normalized_email):
        raise AppException(
            code="EMAIL_ALREADY_IN_USE",
            message="This email is already registered to a coach in your organization",
            status_code=409,
            details=[
                {
                    "field": "email",
                    "message": "This email is already registered to a coach in your organization",
                }
            ],
        )

    if await _email_in_use_by_user(db, normalized_email):
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

    coach_id = uuid4()
    invite_token = secrets.token_urlsafe(32)
    first_name, last_name = _display_name_from_email(normalized_email)
    invite_link = _build_invite_link(invite_token)

    columns = ["id", "org_id", "first_name", "last_name", "email", "role"]
    values = [":id", ":org_id", ":first_name", ":last_name", ":email", ":role"]
    params: dict[str, Any] = {
        "id": coach_id,
        "org_id": organization.id,
        "first_name": first_name,
        "last_name": last_name,
        "email": normalized_email,
        "role": DEFAULT_COACH_ROLE,
    }

    if await _column_exists(db, "invite_token"):
        columns.append("invite_token")
        values.append(":invite_token")
        params["invite_token"] = invite_token

    if await _column_exists(db, "invite_accepted"):
        columns.append("invite_accepted")
        values.append(":invite_accepted")
        params["invite_accepted"] = False

    insert_sql = (
        f"INSERT INTO {COACHES_TABLE} ({', '.join(columns)}) "
        f"VALUES ({', '.join(values)})"
    )

    try:
        await db.execute(text(insert_sql), params)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Failed to invite coach %s: %s", normalized_email, exc)
        if "email" in str(exc).lower() or "unique" in str(exc).lower():
            raise AppException(
                code="EMAIL_ALREADY_IN_USE",
                message="This email is already registered to a coach in your organization",
                status_code=409,
                details=[
                    {
                        "field": "email",
                        "message": "This email is already registered to a coach in your organization",
                    }
                ],
            ) from exc
        raise AppException(
            code="COACH_INVITE_FAILED",
            message="Unable to invite coach",
            status_code=400,
        ) from exc

    try:
        send_coach_invite_email(
            to_email=normalized_email,
            organization_name=organization.name,
            invite_url=invite_link,
        )
    except Exception:
        logger.exception("Failed to send coach invite email to %s", normalized_email)

    logger.info("Org admin %s invited coach %s", user.id, coach_id)
    return {
        "success": True,
        "message": "Coach invitation sent successfully",
        "status": "invited",
        "description": "An invitation email was sent to the coach",
        "link": invite_link,
        "error": None,
        "id": coach_id,
        "email": normalized_email,
        "organization": organization.name,
        "address": organization.address,
        "roles": [DEFAULT_COACH_ROLE, "coach"],
    }


async def search_coaches(
    db: AsyncSession,
    user: User,
    *,
    search_query: str | None,
) -> dict[str, Any]:
    """Search coaches in the organization admin's organization."""
    organization = await require_admin_organization(db, user)
    await _require_coaches_table(db)

    normalized_query = (search_query or "").strip()
    invite_token_exists = await _column_exists(db, "invite_token")
    invite_accepted_exists = await _column_exists(db, "invite_accepted")

    invite_token_select = "invite_token" if invite_token_exists else "NULL AS invite_token"
    invite_accepted_select = (
        "invite_accepted" if invite_accepted_exists else "NULL AS invite_accepted"
    )

    params: dict[str, Any] = {"org_id": organization.id}
    filter_sql = ""
    if normalized_query:
        params["search_term"] = f"%{normalized_query}%"
        filter_sql = """
              AND (
                    first_name ILIKE :search_term
                 OR last_name ILIKE :search_term
                 OR email ILIKE :search_term
                 OR CONCAT(first_name, ' ', last_name) ILIKE :search_term
              )
        """

    result = await db.execute(
        text(
            f"""
            SELECT
                id,
                first_name,
                last_name,
                email,
                role,
                {invite_token_select},
                {invite_accepted_select}
            FROM {COACHES_TABLE}
            WHERE org_id = :org_id
            {filter_sql}
            ORDER BY last_name ASC, first_name ASC
            """
        ),
        params,
    )

    coaches: list[dict[str, Any]] = []
    for row in result.mappings().all():
        payload = dict(row)
        coaches.append(
            {
                "id": payload["id"],
                "name": _coach_display_name(payload),
                "email": payload.get("email"),
                "status": _coach_status(payload),
                "role": payload.get("role"),
            }
        )

    logger.info(
        "Org admin %s searched coaches (%s matches)",
        user.id,
        len(coaches),
    )
    return {
        "success": True,
        "message": "Coaches loaded successfully",
        "status": "ready",
        "description": "Organization coaches matching your search",
        "link": None,
        "error": None,
        "organization": organization.name,
        "address": organization.address,
        "roles": [DEFAULT_COACH_ROLE, "coach"],
        "search_query": normalized_query or None,
        "coaches": coaches,
    }
