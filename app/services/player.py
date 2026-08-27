"""Business logic for coach player detail retrieval and updates."""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.player import PlayerCreateRequest, PlayerUpdateRequest
from app.services import client_db
from app.services.leaderboard import resolve_search_text
from app.services.organization import validate_phone_number
from app.services.profile import validate_profile_email
from app.services.session_summary import compute_shooting_percent

logger = logging.getLogger(__name__)

PLAYERS_TABLE = "players"
TEAMS_TABLE = "teams"

DATE_OF_BIRTH_FORMATS = ("%Y-%m-%d", "%m/%d/%Y")


def _require_non_empty(value: str, field: str, label: str | None = None) -> str:
    """Return trimmed text or raise 400 when a required field is empty."""
    cleaned = (value or "").strip()
    if not cleaned:
        display = label or field.replace("_", " ").title()
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{display} is required",
            status_code=400,
            details=[{"field": field, "message": f"{display} is required"}],
        )
    return cleaned


def parse_player_date_of_birth(value: str) -> date:
    """Parse a player date of birth from ISO or MM/DD/YYYY format."""
    cleaned = _require_non_empty(value, "date_of_birth", "Date of birth")
    for fmt in DATE_OF_BIRTH_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    raise AppException(
        code="VALIDATION_ERROR",
        message="Date of birth must use YYYY-MM-DD or MM/DD/YYYY format",
        status_code=400,
        details=[
            {
                "field": "date_of_birth",
                "message": "Date of birth must use YYYY-MM-DD or MM/DD/YYYY format",
            }
        ],
    )


def format_player_date_of_birth(value: date | None) -> str | None:
    """Format a birthdate for API responses."""
    return value.isoformat() if value is not None else None


def _generate_player_code() -> str:
    """Generate a unique player code for new roster records."""
    return f"PC-{secrets.token_hex(4).upper()}"


async def _column_exists(db: AsyncSession, table_name: str, column_name: str) -> bool:
    """Return True when a column exists on a public table."""
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
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(exists)


async def _teams_table_exists(db: AsyncSession) -> bool:
    """Return True when the teams table is available."""
    return await client_db.table_exists(db, TEAMS_TABLE)


async def _fetch_player_row(db: AsyncSession, player_id: UUID) -> dict[str, Any] | None:
    """Load a single active player row with optional team name."""
    await client_db.require_table(db, PLAYERS_TABLE)

    email_column = await _column_exists(db, PLAYERS_TABLE, "email")
    phone_column = await _column_exists(db, PLAYERS_TABLE, "phone")
    position_column = await _column_exists(db, PLAYERS_TABLE, "position")
    jersey_column = await _column_exists(db, PLAYERS_TABLE, "jersey_number")
    player_code_column = await _column_exists(db, PLAYERS_TABLE, "player_code")
    active_column = await _column_exists(db, PLAYERS_TABLE, "active")
    team_join = await _teams_table_exists(db)

    email_select = "p.email" if email_column else "NULL AS email"
    phone_select = "p.phone" if phone_column else "NULL AS phone"
    position_select = "p.position" if position_column else "NULL AS position"
    jersey_select = "p.jersey_number" if jersey_column else "NULL AS jersey_number"
    player_code_select = "p.player_code" if player_code_column else "NULL AS player_code"
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
                {position_select},
                {jersey_select},
                {player_code_select},
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


async def _fetch_player_stats(db: AsyncSession, player_id: UUID) -> dict[str, int]:
    """Aggregate basketball stats and map them to the player detail cards."""
    if not await client_db.table_exists(db, "session_data"):
        return {
            "games_played": 0,
            "goals": 0,
            "assists": 0,
            "yellow_cards": 0,
            "makes": 0,
            "attempts": 0,
            "shooting_percent": 0,
        }

    result = await db.execute(
        text(
            """
            SELECT
                COUNT(DISTINCT sd.session_id) AS games_played,
                COALESCE(SUM(sd.makes), 0) AS makes,
                COALESCE(SUM(sd.attempts), 0) AS attempts
            FROM session_data sd
            WHERE sd.player_id = :player_id
            """
        ),
        {"player_id": player_id},
    )
    row = result.mappings().first()
    makes = int(row["makes"] or 0) if row is not None else 0
    attempts = int(row["attempts"] or 0) if row is not None else 0
    games_played = int(row["games_played"] or 0) if row is not None else 0

    return {
        "games_played": games_played,
        "goals": makes,
        "assists": 0,
        "yellow_cards": 0,
        "makes": makes,
        "attempts": attempts,
        "shooting_percent": compute_shooting_percent(makes, attempts),
    }


def _build_detail_payload(
    row: dict[str, Any],
    stats: dict[str, int],
    *,
    message: str,
) -> dict[str, Any]:
    """Shape a player detail dict for API responses."""
    first_name = str(row.get("first_name") or "").strip()
    last_name = str(row.get("last_name") or "").strip()
    name = f"{first_name} {last_name}".strip() or "Unknown Player"
    phone_value = row.get("phone")
    player_id = UUID(str(row["id"]))

    return {
        "success": True,
        "message": message,
        "status": "ready",
        "description": "Player profile, statistics, and contact information",
        "title": "Player Details",
        "link": None,
        "error": None,
        "image": None,
        "id": player_id,
        "player_id": player_id,
        "name": name,
        "email": row.get("email"),
        "phone_number": phone_value,
        "phone": phone_value,
        **stats,
        "position": row.get("position"),
        "role": None,
        "team": row.get("team_name"),
        "player_code": row.get("player_code"),
        "jersey_number": (
            str(row["jersey_number"]) if row.get("jersey_number") is not None else None
        ),
    }


def _build_list_item(row: dict[str, Any]) -> dict[str, Any]:
    """Shape a player summary row for My Players list responses."""
    first_name = str(row.get("first_name") or "").strip()
    last_name = str(row.get("last_name") or "").strip()
    name = f"{first_name} {last_name}".strip() or "Unknown Player"
    player_code = row.get("player_code")
    code_value = str(player_code) if player_code is not None else None
    jersey_number = row.get("jersey_number")
    jersey_value = str(jersey_number) if jersey_number is not None else None
    return {
        "id": UUID(str(row["id"])),
        "name": name,
        "code": code_value,
        "player_code": code_value,
        "jersey_number": jersey_value,
        "team_name": row.get("team_name"),
    }


async def _fetch_org_players(
    db: AsyncSession,
    org_id: UUID,
    *,
    search_term: str | None = None,
) -> list[dict[str, Any]]:
    """Load active players for an organization, optionally filtered by search text."""
    await client_db.require_table(db, PLAYERS_TABLE)

    active_column = await _column_exists(db, PLAYERS_TABLE, "active")
    player_code_column = await _column_exists(db, PLAYERS_TABLE, "player_code")
    jersey_column = await _column_exists(db, PLAYERS_TABLE, "jersey_number")
    team_join = await _teams_table_exists(db)

    active_sql = "AND p.active = true" if active_column else ""
    player_code_select = "p.player_code" if player_code_column else "NULL AS player_code"
    jersey_select = "p.jersey_number" if jersey_column else "NULL AS jersey_number"
    team_select = "t.name AS team_name" if team_join else "NULL AS team_name"
    team_join_sql = "LEFT JOIN teams t ON t.id = p.team_id" if team_join else ""

    search_sql = ""
    params: dict[str, Any] = {"org_id": org_id}
    if search_term:
        pattern = f"%{search_term}%"
        params["pattern"] = pattern
        player_code_filter = "OR p.player_code ILIKE :pattern" if player_code_column else ""
        jersey_filter = "OR p.jersey_number ILIKE :pattern" if jersey_column else ""
        search_sql = f"""
              AND (
                    p.first_name ILIKE :pattern
                 OR p.last_name ILIKE :pattern
                 OR TRIM(CONCAT(p.first_name, ' ', p.last_name)) ILIKE :pattern
                 {player_code_filter}
                 {jersey_filter}
              )
        """

    result = await db.execute(
        text(
            f"""
            SELECT
                p.id,
                p.first_name,
                p.last_name,
                {player_code_select},
                {jersey_select},
                {team_select}
            FROM players p
            {team_join_sql}
            WHERE p.org_id = :org_id
              {active_sql}
              {search_sql}
            ORDER BY p.last_name ASC, p.first_name ASC
            LIMIT 50
            """
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()]


def _ensure_coach_org(user: User) -> UUID:
    """Return the coach organization id or raise 400 when missing."""
    if user.org_id is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Coach must belong to an organization to manage players",
            status_code=400,
            details=[
                {
                    "field": "org_id",
                    "message": "Coach must belong to an organization to manage players",
                }
            ],
        )
    return user.org_id


async def _email_in_use_by_other_player(
    db: AsyncSession,
    *,
    org_id: UUID,
    email: str,
    exclude_player_id: UUID,
) -> bool:
    """Return True when another active player in the org already uses the email."""
    if not await _column_exists(db, PLAYERS_TABLE, "email"):
        return False

    active_column = await _column_exists(db, PLAYERS_TABLE, "active")
    active_sql = "AND active = true" if active_column else ""

    result = await db.execute(
        text(
            f"""
            SELECT id
            FROM players
            WHERE org_id = :org_id
              AND LOWER(email) = :email
              AND id != :exclude_player_id
              {active_sql}
            LIMIT 1
            """
        ),
        {"org_id": org_id, "email": email, "exclude_player_id": exclude_player_id},
    )
    return result.scalar_one_or_none() is not None


async def _email_exists_in_org(db: AsyncSession, *, org_id: UUID, email: str) -> bool:
    """Return True when an active player in the org already uses the email."""
    return await _email_in_use_by_other_player(
        db,
        org_id=org_id,
        email=email,
        exclude_player_id=UUID(int=0),
    )


async def _resolve_team_id(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_selection: str,
) -> tuple[UUID | None, str]:
    """Resolve a team id from the selected team name within the coach organization."""
    cleaned = _require_non_empty(team_selection, "team_selection", "Team selection")
    if not await _teams_table_exists(db):
        return None, cleaned

    result = await db.execute(
        text(
            """
            SELECT id, name
            FROM teams
            WHERE org_id = :org_id
              AND name ILIKE :team_name
            LIMIT 1
            """
        ),
        {"org_id": org_id, "team_name": cleaned},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Selected team was not found in your organization",
            status_code=400,
            details=[
                {
                    "field": "team_selection",
                    "message": "Selected team was not found in your organization",
                }
            ],
        )
    return UUID(str(row["id"])), str(row["name"])


def _build_create_response(
    *,
    player_id: UUID,
    first_name: str,
    last_name: str,
    email: str,
    phone_value: str,
    gender: str,
    birthdate: date,
    team_selection: str,
    team_name: str | None,
) -> dict[str, Any]:
    """Shape a player creation dict for API responses."""
    name = f"{first_name} {last_name}".strip()
    return {
        "success": True,
        "message": "Player added successfully",
        "status": "created",
        "description": "The player was added to your roster",
        "title": "Add Player",
        "link": None,
        "error": None,
        "id": player_id,
        "player_id": player_id,
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone_number": phone_value,
        "phone": phone_value,
        "gender": gender,
        "date_of_birth": format_player_date_of_birth(birthdate),
        "team_selection": team_selection,
        "team": team_name or team_selection,
    }


async def create_player(
    db: AsyncSession,
    user: User,
    payload: PlayerCreateRequest,
) -> dict[str, Any]:
    """Create a new player record scoped to the authenticated coach's organization."""
    org_id = _ensure_coach_org(user)
    await client_db.require_table(db, PLAYERS_TABLE)

    first_name = _require_non_empty(payload.first_name, "first_name", "First name")
    last_name = _require_non_empty(payload.last_name, "last_name", "Last name")
    email = validate_profile_email(payload.email)
    phone_value = validate_phone_number(_require_non_empty(payload.phone_number, "phone_number", "Phone number"))
    gender = _require_non_empty(payload.gender, "gender", "Gender")
    birthdate = parse_player_date_of_birth(payload.date_of_birth)
    team_id, team_name = await _resolve_team_id(db, org_id=org_id, team_selection=payload.team_selection)

    if await _email_exists_in_org(db, org_id=org_id, email=email):
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

    player_id = uuid4()
    player_code = _generate_player_code()
    insert_values: dict[str, Any] = {
        "id": player_id,
        "org_id": org_id,
        "first_name": first_name,
        "last_name": last_name,
        "player_code": player_code,
        "email": email,
        "phone": phone_value,
        "gender": gender,
        "birthdate": birthdate,
        "team_id": team_id,
        "active": True,
    }

    columns: list[str] = []
    params: dict[str, Any] = {}
    for column_name, value in insert_values.items():
        if value is None:
            continue
        if not await _column_exists(db, PLAYERS_TABLE, column_name):
            continue
        columns.append(column_name)
        params[column_name] = value

    placeholders = ", ".join(f":{column}" for column in columns)
    column_sql = ", ".join(columns)
    await db.execute(
        text(
            f"""
            INSERT INTO players ({column_sql})
            VALUES ({placeholders})
            """
        ),
        params,
    )
    await db.commit()

    logger.info("Created player %s for org %s by coach %s", player_id, org_id, user.id)
    return _build_create_response(
        player_id=player_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_value=phone_value,
        gender=gender,
        birthdate=birthdate,
        team_selection=payload.team_selection.strip(),
        team_name=team_name,
    )


async def get_player_detail(db: AsyncSession, player_id: UUID) -> dict[str, Any]:
    """Return player details for public read access."""
    row = await _fetch_player_row(db, player_id)
    if row is None:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[{"field": "player_id", "message": "Player not found"}],
        )

    stats = await _fetch_player_stats(db, player_id)
    return _build_detail_payload(row, stats, message="Player details loaded successfully")


async def list_players(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return active players for the authenticated coach's organization."""
    org_id = _ensure_coach_org(user)
    rows = await _fetch_org_players(db, org_id)
    players = [_build_list_item(row) for row in rows]
    logger.info("Listed %s players for coach %s", len(players), user.id)
    return {
        "success": True,
        "message": "Players loaded successfully",
        "status": "ready",
        "description": "Active players in your organization",
        "title": "My Players",
        "link": None,
        "error": None,
        "players": players,
    }


async def search_players(
    db: AsyncSession,
    user: User,
    *,
    search_query: str | None,
    full_name: str | None,
    phone: str | None = None,
) -> dict[str, Any]:
    """Search active players by name or player code within the coach organization."""
    org_id = _ensure_coach_org(user)
    term = resolve_search_text(search_query=search_query, full_name=full_name)
    rows = await _fetch_org_players(db, org_id, search_term=term)
    players = [_build_list_item(row) for row in rows]
    logger.info("Player search for coach %s returned %s results", user.id, len(players))
    return {
        "success": True,
        "message": "Search results loaded successfully",
        "status": "ready",
        "description": f"Players matching '{term}'",
        "title": "My Players",
        "link": None,
        "error": None,
        "search_query": term,
        "full_name": full_name.strip() if full_name and full_name.strip() else None,
        "phone": phone,
        "players": players,
    }


async def get_player_detail_for_coach(
    db: AsyncSession,
    user: User,
    player_id: UUID,
) -> dict[str, Any]:
    """Return player details scoped to the authenticated coach's organization."""
    org_id = _ensure_coach_org(user)
    row = await _fetch_player_row(db, player_id)
    if row is None or UUID(str(row["org_id"])) != org_id:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[{"field": "player_id", "message": "Player not found"}],
        )

    stats = await _fetch_player_stats(db, player_id)
    return _build_detail_payload(row, stats, message="Player details loaded successfully")


async def update_player(
    db: AsyncSession,
    user: User,
    player_id: UUID,
    payload: PlayerUpdateRequest,
) -> dict[str, Any]:
    """Update a player record scoped to the authenticated coach's organization."""
    org_id = _ensure_coach_org(user)
    row = await _fetch_player_row(db, player_id)
    if row is None or UUID(str(row["org_id"])) != org_id:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[{"field": "player_id", "message": "Player not found"}],
        )

    updates: dict[str, Any] = {}

    if payload.first_name is not None:
        cleaned = payload.first_name.strip()
        if not cleaned:
            raise AppException(
                code="VALIDATION_ERROR",
                message="First name cannot be empty",
                status_code=400,
                details=[{"field": "first_name", "message": "First name cannot be empty"}],
            )
        updates["first_name"] = cleaned

    if payload.last_name is not None:
        cleaned = payload.last_name.strip()
        if not cleaned:
            raise AppException(
                code="VALIDATION_ERROR",
                message="Last name cannot be empty",
                status_code=400,
                details=[{"field": "last_name", "message": "Last name cannot be empty"}],
            )
        updates["last_name"] = cleaned

    if payload.email is not None:
        normalized_email = validate_profile_email(str(payload.email))
        if await _email_in_use_by_other_player(
            db,
            org_id=org_id,
            email=normalized_email,
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
        updates["email"] = normalized_email

    if payload.phone_number is not None:
        cleaned_phone = payload.phone_number.strip()
        if cleaned_phone:
            updates["phone"] = validate_phone_number(cleaned_phone)
        else:
            updates["phone"] = None

    if payload.position is not None:
        cleaned_position = payload.position.strip()
        updates["position"] = cleaned_position or None

    if not updates:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one player field must be provided",
            status_code=400,
            details=[
                {
                    "field": "body",
                    "message": "At least one player field must be provided",
                }
            ],
        )

    set_clauses = ", ".join(f"{column} = :{column}" for column in updates)
    await db.execute(
        text(
            f"""
            UPDATE players
            SET {set_clauses}
            WHERE id = :player_id
              AND org_id = :org_id
            """
        ),
        {"player_id": player_id, "org_id": org_id, **updates},
    )
    await db.commit()

    logger.info("Updated player %s for org %s by coach %s", player_id, org_id, user.id)
    detail = await get_player_detail(db, player_id)
    detail["message"] = "Player updated successfully"
    return detail


async def delete_player(
    db: AsyncSession,
    user: User,
    player_id: UUID,
) -> dict[str, Any]:
    """Soft-delete a player by setting active=false."""
    org_id = _ensure_coach_org(user)
    row = await _fetch_player_row(db, player_id)
    if row is None or UUID(str(row["org_id"])) != org_id:
        raise AppException(
            code="PLAYER_NOT_FOUND",
            message="Player not found",
            status_code=404,
            details=[{"field": "player_id", "message": "Player not found"}],
        )

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
    await db.commit()

    logger.info("Removed player %s from org %s by coach %s", player_id, org_id, user.id)
    return {
        "success": True,
        "message": "Player removed successfully",
        "status": "ready",
        "description": "The player was removed from the roster",
        "title": "Player Details",
        "link": None,
        "error": None,
        "id": player_id,
        "player_id": player_id,
    }
