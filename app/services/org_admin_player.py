"""Business logic for organization admin player management."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.player import PlayerUpdateRequest
from app.services import player as player_service
from app.services.org_admin_profile import require_admin_organization

logger = logging.getLogger(__name__)

_STAT_KEYS = ("games_played", "goals", "assists", "yellow_cards")
_COACH_ONLY_DETAIL_KEYS = (
    "makes",
    "attempts",
    "shooting_percent",
    "player_id",
    "name",
    "role",
    "player_code",
    "jersey_number",
    "image",
)


def _to_org_admin_detail_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map coach player detail payloads to the org-admin Player Details contract."""
    stats = {key: int(payload.pop(key, 0)) for key in _STAT_KEYS}
    for key in _COACH_ONLY_DETAIL_KEYS:
        payload.pop(key, None)

    phone_metadata = payload.pop("phone", None)
    payload["stats"] = stats
    payload["title"] = "Player Management"
    payload["phone"] = phone_metadata
    return payload


async def get_player_detail(
    db: AsyncSession,
    user: User,
    player_id: UUID,
) -> dict[str, Any]:
    """Return player details scoped to the authenticated org admin's organization."""
    await require_admin_organization(db, user)
    base = await player_service.get_player_detail_for_coach(db, user, player_id)
    logger.info("Org admin %s loaded player %s", user.id, player_id)
    return _to_org_admin_detail_payload(base)


async def list_players(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return active players for the authenticated org admin's organization."""
    await require_admin_organization(db, user)
    base = await player_service.list_players(db, user)
    base["title"] = "Player Management"
    base["description"] = "Active players in your organization"
    logger.info("Org admin %s listed %s players", user.id, len(base.get("players", [])))
    return base


async def update_player(
    db: AsyncSession,
    user: User,
    player_id: UUID,
    payload: PlayerUpdateRequest,
) -> dict[str, Any]:
    """Update a player record scoped to the authenticated org admin's organization."""
    await require_admin_organization(db, user)
    base = await player_service.update_player(db, user, player_id, payload)
    logger.info("Org admin %s updated player %s", user.id, player_id)
    return _to_org_admin_detail_payload(base)


async def get_player_removal_detail(
    db: AsyncSession,
    user: User,
    player_id: UUID,
) -> dict[str, Any]:
    """Return player details and confirmation copy for the Remove Player screen."""
    from app.schemas.player_removal import REMOVAL_CONFIRMATION_MESSAGE
    from app.services.player_removal import _fetch_player_row_for_removal

    organization = await require_admin_organization(db, user)
    row = await _fetch_player_row_for_removal(db, player_id)
    if row is None or UUID(str(row["org_id"])) != organization.id:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[{"field": "player_id", "message": "Player not found"}],
        )

    first_name = str(row.get("first_name") or "").strip()
    last_name = str(row.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip() or "Unknown Player"
    phone_value = row.get("phone")

    logger.info("Org admin %s loaded removal detail for player %s", user.id, player_id)
    return {
        "success": True,
        "message": "Confirm player removal",
        "status": "confirm",
        "description": REMOVAL_CONFIRMATION_MESSAGE,
        "title": "Remove Player",
        "link": None,
        "error": None,
        "id": player_id,
        "player_id": player_id,
        "name": full_name,
        "full_name": full_name,
        "email": row.get("email"),
        "phone_number": phone_value,
        "phone": phone_value,
        "team": row.get("team_name"),
        "organization": organization.name,
        "confirmation_message": REMOVAL_CONFIRMATION_MESSAGE,
    }


async def remove_player_by_id(
    db: AsyncSession,
    user: User,
    player_id: UUID,
    *,
    full_name: str,
    email: str,
    phone: str,
) -> dict[str, Any]:
    """Remove a player after validating identity fields against the target record."""
    from app.services import player_removal as player_removal_service

    organization = await require_admin_organization(db, user)
    org_id = organization.id

    validated_name = player_removal_service._validate_full_name(full_name)
    validated_email = player_removal_service._validate_removal_email(email)
    phone_digits = player_removal_service._validate_removal_phone(phone)

    row = await player_removal_service._fetch_player_row_for_removal(db, player_id)
    if row is None or UUID(str(row["org_id"])) != org_id:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[{"field": "player_id", "message": "Player not found"}],
        )

    if await player_service._email_in_use_by_other_player(
        db,
        org_id=org_id,
        email=validated_email,
        exclude_player_id=player_id,
    ):
        raise AppException(
            code="EMAIL_ALREADY_IN_USE",
            message="This email is already registered to another player",
            status_code=409,
            details=[
                {
                    "field": "email",
                    "message": "This email is already registered to another player",
                }
            ],
        )

    stored_email = str(row.get("email") or "").strip().lower()
    if stored_email != validated_email.lower():
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

    if not player_removal_service._names_match(row, validated_name) or not player_removal_service._phones_match(
        row.get("phone"),
        phone_digits,
    ):
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="No matching player was found for the provided details",
            status_code=409,
            details=[
                {
                    "field": "full_name",
                    "message": "No matching player was found for the provided details",
                }
            ],
        )

    await player_removal_service._soft_delete_player(db, org_id=org_id, player_id=player_id)
    await db.commit()

    logger.info("Org admin %s removed player %s from org %s", user.id, player_id, org_id)
    return {
        "success": True,
        "message": "Player removed successfully",
        "status": "removed",
        "description": "The player was removed from the organization",
        "title": "Remove Player",
        "link": None,
        "error": None,
        "id": player_id,
        "player_id": player_id,
        "name": validated_name,
        "full_name": validated_name,
        "email": validated_email,
        "phone": phone.strip(),
        "organization": organization.name,
    }
