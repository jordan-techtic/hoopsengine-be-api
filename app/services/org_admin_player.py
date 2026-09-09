"""Business logic for organization admin player management."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.player import PlayerUpdateRequest
from app.services import client_db
from app.services import player as player_service
from app.services.org_admin_profile import require_admin_organization

logger = logging.getLogger(__name__)

PLAYERS_TABLE = "players"

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

    first_name = str(payload.get("first_name") or "").strip()
    last_name = str(payload.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip() or "Unknown Player"
    team_name = payload.get("team")
    phone_value = payload.get("phone_number") or payload.pop("phone", None)

    payload["name"] = full_name
    payload["full_name"] = full_name
    payload["team_assignment"] = team_name
    payload["phone"] = phone_value
    payload["phone_number"] = phone_value
    payload["stats"] = stats
    payload["title"] = "Player Management"
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


def _validate_optional_phone(phone: str | None) -> None:
    """Validate optional Figma status-bar phone metadata when provided."""
    if phone is None or not phone.strip():
        return
    cleaned = phone.strip()
    if len(cleaned) > 30:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number is invalid",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number is invalid"}],
        )
    if not re.sub(r"\D", "", cleaned):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number must contain at least one digit",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number must contain at least one digit"}],
        )


def _validate_player_code(player_code: str) -> str:
    """Return normalized player code or raise 400 when empty."""
    cleaned = (player_code or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Player code is required",
            status_code=400,
            details=[{"field": "player_code", "message": "Player code is required"}],
        )
    return cleaned


def _player_status_from_row(row: dict[str, Any]) -> Literal["active", "inactive"]:
    """Map a database row to the roster status badge value."""
    active_value = row.get("active")
    if active_value is None:
        return "active"
    return "active" if bool(active_value) else "inactive"


def _build_org_admin_list_item(row: dict[str, Any]) -> dict[str, Any]:
    """Shape a player summary row for the org-admin Player Listing screen."""
    first_name = str(row.get("first_name") or "").strip()
    last_name = str(row.get("last_name") or "").strip()
    name = f"{first_name} {last_name}".strip() or "Unknown Player"
    player_code = row.get("player_code")
    code_value = str(player_code) if player_code is not None else None
    team_name = row.get("team_name")
    roster_status = _player_status_from_row(row)
    return {
        "id": UUID(str(row["id"])),
        "name": name,
        "code": code_value,
        "player_code": code_value,
        "status": roster_status,
        "team": team_name,
        "team_name": team_name,
    }


async def _fetch_org_admin_player_rows(
    db: AsyncSession,
    org_id: UUID,
    *,
    active_only: bool = True,
    player_code: str | None = None,
    player_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Load players for an organization with optional active and player-code filters."""
    await client_db.require_table(db, PLAYERS_TABLE)

    active_column = await player_service._column_exists(db, PLAYERS_TABLE, "active")
    player_code_column = await player_service._column_exists(db, PLAYERS_TABLE, "player_code")
    team_join = await player_service._teams_table_exists(db)

    filters = ["p.org_id = :org_id"]
    params: dict[str, Any] = {"org_id": org_id}

    if active_only and active_column:
        filters.append("p.active = true")

    if player_code:
        if not player_code_column:
            return []
        filters.append("p.player_code ILIKE :player_code_pattern")
        params["player_code_pattern"] = f"%{player_code.strip()}%"

    if player_id is not None:
        filters.append("p.id = :player_id")
        params["player_id"] = player_id

    player_code_select = "p.player_code" if player_code_column else "NULL AS player_code"
    active_select = "p.active" if active_column else "true AS active"
    team_select = "t.name AS team_name" if team_join else "NULL AS team_name"
    team_join_sql = "LEFT JOIN teams t ON t.id = p.team_id" if team_join else ""
    where_sql = " AND ".join(filters)

    result = await db.execute(
        text(
            f"""
            SELECT
                p.id,
                p.first_name,
                p.last_name,
                {player_code_select},
                {active_select},
                {team_select}
            FROM players p
            {team_join_sql}
            WHERE {where_sql}
            ORDER BY p.last_name ASC, p.first_name ASC
            LIMIT 50
            """
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()]


async def list_players(
    db: AsyncSession,
    user: User,
    *,
    phone: str | None = None,
) -> dict[str, Any]:
    """Return active players for the authenticated org admin's organization."""
    _validate_optional_phone(phone)
    organization = await require_admin_organization(db, user)
    rows = await _fetch_org_admin_player_rows(db, organization.id, active_only=True)
    players = [_build_org_admin_list_item(row) for row in rows]
    logger.info("Org admin %s listed %s players", user.id, len(players))
    return {
        "success": True,
        "message": "Players loaded successfully",
        "status": "ready",
        "description": "Active players in your organization",
        "title": "Player Management",
        "link": None,
        "error": None,
        "organization": organization.name,
        "phone": phone,
        "players": players,
    }


async def search_players_by_code(
    db: AsyncSession,
    user: User,
    *,
    player_code: str,
    phone: str | None = None,
) -> dict[str, Any]:
    """Search active players by player code within the org admin's organization."""
    _validate_optional_phone(phone)
    normalized_code = _validate_player_code(player_code)
    organization = await require_admin_organization(db, user)
    rows = await _fetch_org_admin_player_rows(
        db,
        organization.id,
        active_only=True,
        player_code=normalized_code,
    )
    players = [_build_org_admin_list_item(row) for row in rows]
    logger.info(
        "Org admin %s searched player code '%s' and found %s matches",
        user.id,
        normalized_code,
        len(players),
    )
    return {
        "success": True,
        "message": "Player search completed successfully",
        "status": "ready",
        "description": f"Players matching player code '{normalized_code}'",
        "title": "Player Management",
        "link": None,
        "error": None,
        "organization": organization.name,
        "player_code": normalized_code,
        "phone": phone,
        "players": players,
    }


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


async def update_player_status(
    db: AsyncSession,
    user: User,
    player_id: UUID,
    *,
    status: Literal["active", "inactive"],
    phone: str | None = None,
) -> dict[str, Any]:
    """Update a player's roster status within the org admin's organization."""
    _validate_optional_phone(phone)
    organization = await require_admin_organization(db, user)
    rows = await _fetch_org_admin_player_rows(
        db,
        organization.id,
        active_only=False,
        player_id=player_id,
    )
    if not rows:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[{"field": "player_id", "message": "Player not found"}],
        )
    row = rows[0]

    active_column = await player_service._column_exists(db, PLAYERS_TABLE, "active")
    if active_column:
        await db.execute(
            text(
                """
                UPDATE players
                SET active = :active
                WHERE id = :player_id
                  AND org_id = :org_id
                """
            ),
            {
                "active": status == "active",
                "player_id": player_id,
                "org_id": organization.id,
            },
        )
        await db.commit()

    list_item = _build_org_admin_list_item({**row, "active": status == "active"})
    logger.info("Org admin %s updated player %s status to %s", user.id, player_id, status)
    return {
        "success": True,
        "message": "Player status updated successfully",
        "status": status,
        "description": "Player roster status was updated",
        "title": "Player Management",
        "link": None,
        "error": None,
        "organization": organization.name,
        "id": player_id,
        "name": list_item["name"],
        "code": list_item["code"],
        "player_code": list_item["player_code"],
        "team": list_item["team"],
        "phone": phone,
    }


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
