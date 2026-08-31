"""Business logic for coach Remove Player flow."""

from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.player_removal import (
    REMOVAL_CONFIRMATION_MESSAGE,
    PlayerRemovalRequest,
)
from app.services import client_db
from app.services.account_settings import validate_numeric_phone
from app.services.player import PLAYERS_TABLE, TEAMS_TABLE, _column_exists, _ensure_coach_org
from app.services.profile import validate_profile_email

logger = logging.getLogger(__name__)


def _validate_full_name(full_name: str) -> str:
    """Return trimmed full name or raise 400 when empty."""
    cleaned = (full_name or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Full name is required",
            status_code=400,
            details=[{"field": "full_name", "message": "Full name is required"}],
        )
    return cleaned


def _validate_removal_email(email: str) -> str:
    """Return normalized email or raise 400 when empty or invalid."""
    if not (email or "").strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Email is required",
            status_code=400,
            details=[{"field": "email", "message": "Email is required"}],
        )
    return validate_profile_email(email)


def _validate_removal_phone(phone: str) -> str:
    """Return digit-only phone or raise 400 when empty or invalid."""
    if not (phone or "").strip():
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number is required",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number is required"}],
        )
    return validate_numeric_phone(phone)


def _phone_digits(value: str | None) -> str:
    """Strip non-digit characters from a stored phone value."""
    return re.sub(r"\D", "", value or "")


def _phones_match(stored_phone: str | None, provided_digits: str) -> bool:
    """Compare stored and submitted phones allowing formatting/country-code differences."""
    stored_digits = _phone_digits(stored_phone)
    if not stored_digits or not provided_digits:
        return False
    if stored_digits == provided_digits:
        return True
    return stored_digits.endswith(provided_digits) or provided_digits.endswith(stored_digits)


def _names_match(row: dict[str, Any], full_name: str) -> bool:
    """Return True when the stored player name matches the submitted full name."""
    first_name = str(row.get("first_name") or "").strip()
    last_name = str(row.get("last_name") or "").strip()
    expected = f"{first_name} {last_name}".strip().lower()
    return expected == full_name.strip().lower()


def _preview_fields_valid(
    *,
    full_name: str | None,
    email: str | None,
    phone: str | None,
) -> bool:
    """Return True when all preview fields are present and syntactically valid."""
    try:
        if full_name is None or not full_name.strip():
            return False
        _validate_full_name(full_name)
        if email is None or not email.strip():
            return False
        _validate_removal_email(email)
        if phone is None or not phone.strip():
            return False
        _validate_removal_phone(phone)
    except AppException:
        return False
    return True


async def _fetch_player_row_for_removal(
    db: AsyncSession,
    player_id: UUID,
) -> dict[str, Any] | None:
    """Load a single active player row with optional team name for removal flows."""
    await client_db.require_table(db, PLAYERS_TABLE)

    email_column = await _column_exists(db, PLAYERS_TABLE, "email")
    phone_column = await _column_exists(db, PLAYERS_TABLE, "phone")
    active_column = await _column_exists(db, PLAYERS_TABLE, "active")
    team_join = await client_db.table_exists(db, TEAMS_TABLE)

    email_select = "p.email" if email_column else "NULL AS email"
    phone_select = "p.phone" if phone_column else "NULL AS phone"
    team_select = "t.name AS team_name" if team_join else "NULL AS team_name"
    team_join_sql = "LEFT JOIN teams t ON t.id = p.team_id" if team_join else ""
    active_sql = "AND p.active = true" if active_column else ""

    result = await db.execute(
        text(
            f"""
            SELECT
                p.id,
                p.org_id,
                p.first_name,
                p.last_name,
                {email_select},
                {phone_select},
                {team_select}
            FROM players p
            {team_join_sql}
            WHERE p.id = :player_id
              {active_sql}
            LIMIT 1
            """
        ),
        {"player_id": player_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _fetch_org_players_by_email(
    db: AsyncSession,
    *,
    org_id: UUID,
    email: str,
) -> list[dict[str, Any]]:
    """Load active players in the org matching the normalized email."""
    await client_db.require_table(db, PLAYERS_TABLE)

    email_column = await _column_exists(db, PLAYERS_TABLE, "email")
    phone_column = await _column_exists(db, PLAYERS_TABLE, "phone")
    active_column = await _column_exists(db, PLAYERS_TABLE, "active")

    if not email_column:
        return []

    phone_select = "phone" if phone_column else "NULL AS phone"
    active_sql = "AND active = true" if active_column else ""

    result = await db.execute(
        text(
            f"""
            SELECT id, org_id, first_name, last_name, email, {phone_select}
            FROM players
            WHERE org_id = :org_id
              AND LOWER(email) = :email
              {active_sql}
            """
        ),
        {"org_id": org_id, "email": email},
    )
    return [dict(row) for row in result.mappings().all()]


async def _find_player_for_removal(
    db: AsyncSession,
    *,
    org_id: UUID,
    full_name: str,
    email: str,
    phone_digits: str,
) -> dict[str, Any]:
    """Locate a player by org-scoped email, phone, and full name."""
    candidates = await _fetch_org_players_by_email(db, org_id=org_id, email=email)
    matches = [
        row
        for row in candidates
        if _names_match(row, full_name) and _phones_match(row.get("phone"), phone_digits)
    ]

    if not matches:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="No matching player was found for the provided details",
            status_code=409,
            details=[
                {
                    "field": "email",
                    "message": "No matching player was found for the provided details",
                }
            ],
        )

    if len(matches) > 1:
        raise AppException(
            code="PLAYER_REMOVAL_AMBIGUOUS",
            message="Multiple players match the provided details",
            status_code=409,
            details=[
                {
                    "field": "email",
                    "message": "Multiple players match the provided details",
                }
            ],
        )

    return matches[0]


async def _soft_delete_player(
    db: AsyncSession,
    *,
    org_id: UUID,
    player_id: UUID,
) -> None:
    """Soft-delete a player when supported, otherwise hard-delete."""
    active_column = await _column_exists(db, PLAYERS_TABLE, "active")
    if active_column:
        await db.execute(
            text(
                """
                UPDATE players
                SET active = false
                WHERE id = :player_id
                  AND org_id = :org_id
                """
            ),
            {"player_id": player_id, "org_id": org_id},
        )
    else:
        await db.execute(
            text(
                """
                DELETE FROM players
                WHERE id = :player_id
                  AND org_id = :org_id
                """
            ),
            {"player_id": player_id, "org_id": org_id},
        )


def get_removal_confirmation(
    *,
    full_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return confirmation modal copy for the Remove Player screen."""
    can_remove = _preview_fields_valid(full_name=full_name, email=email, phone=phone)
    return {
        "success": True,
        "message": "Confirm player removal",
        "status": "confirm",
        "description": REMOVAL_CONFIRMATION_MESSAGE,
        "title": "Remove Player",
        "link": None,
        "error": None,
        "confirmation_message": REMOVAL_CONFIRMATION_MESSAGE,
        "can_remove": can_remove,
        "name": full_name.strip() if full_name and full_name.strip() else None,
        "email": email.strip() if email and email.strip() else None,
        "phone": phone.strip() if phone and phone.strip() else None,
    }


async def remove_player_by_credentials(
    db: AsyncSession,
    user: User,
    payload: PlayerRemovalRequest,
) -> dict[str, Any]:
    """Remove a player after validating email, phone, and full name."""
    org_id = _ensure_coach_org(user)
    full_name = _validate_full_name(payload.full_name)
    email = _validate_removal_email(payload.email)
    phone_digits = _validate_removal_phone(payload.phone)

    row = await _find_player_for_removal(
        db,
        org_id=org_id,
        full_name=full_name,
        email=email,
        phone_digits=phone_digits,
    )
    player_id = UUID(str(row["id"]))

    await _soft_delete_player(db, org_id=org_id, player_id=player_id)
    await db.commit()

    logger.info(
        "Removed player %s from org %s by coach %s via remove_player credentials",
        player_id,
        org_id,
        user.id,
    )
    return {
        "success": True,
        "message": "Player removed successfully",
        "status": "removed",
        "description": "The player was removed from the roster",
        "title": "Remove Player",
        "link": None,
        "error": None,
        "id": player_id,
        "player_id": player_id,
        "name": full_name,
        "full_name": full_name,
        "email": email,
        "phone": phone_digits,
    }
