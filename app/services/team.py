"""Business logic for Team Details APIs (/api/v1/teams)."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.organization import Organization
from app.models.user import User
from app.schemas.org_admin_team import OrgAdminTeamCreateRequest, OrgAdminTeamUpdateRequest
from app.schemas.team import TeamCreateRequest, TeamUpdateRequest
from app.services import client_db
from app.services import org_admin_team as org_admin_team_service
from app.services.org_admin_profile import require_admin_organization
from app.services.account_settings import split_full_name
from app.services.organization import build_pagination_meta, get_organization_by_id
from app.services.profile import validate_profile_email

logger = logging.getLogger(__name__)

TEAMS_TABLE = org_admin_team_service.TEAMS_TABLE
COACHES_TABLE = org_admin_team_service.COACHES_TABLE
PLAYERS_TABLE = org_admin_team_service.PLAYERS_TABLE

DEFAULT_DESCRIPTION = "Team Details"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


async def _require_user_organization(db: AsyncSession, user: User) -> Organization:
    """Return the authenticated user's organization or raise 404."""
    if user.org_id is None:
        raise AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization profile not found",
            status_code=404,
        )
    organization = await get_organization_by_id(db, user.org_id)
    if organization is None:
        raise AppException(
            code="ORGANIZATION_NOT_FOUND",
            message="Organization profile not found",
            status_code=404,
        )
    return organization


def _validate_required_name(name: str | None) -> str:
    """Return trimmed team name or raise 400 when empty."""
    cleaned = (name or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Team name is required",
            status_code=400,
            details=[{"field": "name", "message": "Team name is required"}],
        )
    return cleaned


def _validate_required_email(email: str | None) -> str:
    """Return normalized email or raise 400 when empty or invalid."""
    cleaned = (email or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Email is required",
            status_code=400,
            details=[{"field": "email", "message": "Email is required"}],
        )
    return validate_profile_email(cleaned)


def _validate_required_age_group(age_group: str | None) -> str:
    """Return trimmed age group or raise 400 when empty."""
    cleaned = (age_group or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Age group is required",
            status_code=400,
            details=[{"field": "age_group", "message": "Age group is required"}],
        )
    return cleaned


def _validate_required_members(names: list[str], *, field: str, label: str) -> None:
    """Raise 400 when a required roster list is empty."""
    if names:
        return
    raise AppException(
        code="VALIDATION_ERROR",
        message=f"At least one {label} is required",
        status_code=400,
        details=[{"field": field, "message": f"At least one {label} is required"}],
    )


def _normalize_page(page: int) -> int:
    """Clamp list page numbers to valid 1-based values."""
    return max(page, 1)


def _normalize_page_size(page_size: int) -> int:
    """Clamp page size to supported bounds."""
    if page_size < 1:
        return DEFAULT_PAGE_SIZE
    return min(page_size, MAX_PAGE_SIZE)


def _derive_team_code(team_name: str) -> str:
    """Generate a unique-enough team code from the display name."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", team_name.strip()).strip("-").upper()
    slug = slug[:16] or "TEAM"
    return f"{slug}-{uuid4().hex[:6].upper()}"


async def _email_exists_in_system(db: AsyncSession, *, email: str) -> bool:
    """Return True when the email is already registered to a user account."""
    result = await db.execute(select(User.id).where(User.email == email))
    return result.scalar_one_or_none() is not None


async def _coach_email_exists_in_org(
    db: AsyncSession,
    *,
    org_id: UUID,
    email: str,
    exclude_coach_id: UUID | None = None,
) -> bool:
    """Return True when a coach in the organization already uses the email."""
    if not await client_db.table_exists(db, COACHES_TABLE):
        return False

    params: dict[str, Any] = {"org_id": org_id, "email": email.lower()}
    if exclude_coach_id is not None:
        params["exclude_coach_id"] = exclude_coach_id
        exists_sql = """
            SELECT EXISTS (
                SELECT 1
                FROM coaches
                WHERE org_id = :org_id
                  AND email ILIKE :email
                  AND id <> :exclude_coach_id
            )
            """
    else:
        exists_sql = """
            SELECT EXISTS (
                SELECT 1
                FROM coaches
                WHERE org_id = :org_id
                  AND email ILIKE :email
            )
            """

    exists = await db.scalar(text(exists_sql), params)
    return bool(exists)


async def _fetch_linked_user_phone(db: AsyncSession, *, email: str | None) -> str | None:
    """Return phone from a user account matching the coach email."""
    if not email:
        return None
    result = await db.execute(select(User.phone).where(User.email == email))
    return result.scalar_one_or_none()


async def _fetch_team_coach_names(db: AsyncSession, *, team_id: UUID, org_id: UUID) -> list[str]:
    """Return coach display names assigned to a team."""
    if not await client_db.table_exists(db, COACHES_TABLE):
        return []

    result = await db.execute(
        text("""
            SELECT first_name, last_name, role
            FROM coaches
            WHERE team_id = :team_id
              AND org_id = :org_id
            ORDER BY created_at ASC NULLS LAST, last_name ASC, first_name ASC
            """
        ),
        {"team_id": team_id, "org_id": org_id},
    )

    names: list[str] = []
    for row in result.mappings().all():
        first_name = str(row.get("first_name") or "").strip()
        last_name = str(row.get("last_name") or "").strip()
        display = " ".join(part for part in (first_name, last_name) if part).strip()
        names.append(display or "Coach")
    return names


async def _fetch_team_player_names(db: AsyncSession, *, team_id: UUID, org_id: UUID) -> list[str]:
    """Return player display names assigned to a team."""
    if not await client_db.table_exists(db, PLAYERS_TABLE):
        return []

    result = await db.execute(
        text("""
            SELECT first_name, last_name
            FROM players
            WHERE team_id = :team_id
              AND org_id = :org_id
            ORDER BY last_name ASC, first_name ASC
            """
        ),
        {"team_id": team_id, "org_id": org_id},
    )

    names: list[str] = []
    for row in result.mappings().all():
        first_name = str(row.get("first_name") or "").strip()
        last_name = str(row.get("last_name") or "").strip()
        display = " ".join(part for part in (first_name, last_name) if part).strip()
        if display:
            names.append(display)
    return names


async def _fetch_primary_coach(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
) -> dict[str, Any] | None:
    """Return the earliest assigned coach row for a team."""
    if not await client_db.table_exists(db, COACHES_TABLE):
        return None

    result = await db.execute(
        text("""
            SELECT id, first_name, last_name, email, role
            FROM coaches
            WHERE team_id = :team_id
              AND org_id = :org_id
            ORDER BY created_at ASC NULLS LAST
            LIMIT 1
            """
        ),
        {"team_id": team_id, "org_id": org_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _fetch_team_roles(db: AsyncSession, *, team_id: UUID, org_id: UUID) -> list[str]:
    """Return distinct coach role labels for a team."""
    if not await client_db.table_exists(db, COACHES_TABLE):
        return []

    result = await db.execute(
        text("""
            SELECT DISTINCT role
            FROM coaches
            WHERE team_id = :team_id
              AND org_id = :org_id
              AND role IS NOT NULL
              AND TRIM(role) <> ''
            ORDER BY role ASC
            """
        ),
        {"team_id": team_id, "org_id": org_id},
    )
    return [str(row[0]) for row in result.all()]


async def _set_team_season(
    db: AsyncSession,
    *,
    team_id: UUID,
    season: str | None,
) -> None:
    """Persist season when the column exists."""
    if season is None:
        return

    await db.execute(
        text("UPDATE teams SET season = :season WHERE id = :team_id"),
        {"team_id": team_id, "season": season.strip() or None},
    )
    await db.commit()


def _metadata_only(value: str | None) -> str | None:
    """Normalize optional metadata text."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _build_team_details_response(
    *,
    row: dict[str, Any],
    organization_name: str,
    message: str,
    coach_names: list[str],
    player_names: list[str],
    primary_coach: dict[str, Any] | None,
    roles: list[str],
    phone_number: str | None,
    home_ground: str | None = None,
    training_schedule: str | None = None,
    founded: date | None = None,
) -> dict[str, Any]:
    """Shape the Team Details API envelope."""
    team_name = str(row["name"])
    season = row.get("season")
    season_text = str(season).strip() if season is not None else None
    if season_text == "":
        season_text = None

    age_group = row.get("level")
    age_group_text = str(age_group).strip() if age_group is not None else None
    if age_group_text == "":
        age_group_text = None

    description = row.get("description")
    description_text = str(description).strip() if description is not None else None

    email = str(primary_coach.get("email")).strip() if primary_coach and primary_coach.get("email") else None
    role = str(primary_coach.get("role")).strip() if primary_coach and primary_coach.get("role") else None

    return {
        "success": True,
        "message": message,
        "status": "active",
        "description": description_text or DEFAULT_DESCRIPTION,
        "link": None,
        "error": None,
        "id": row["id"],
        "name": team_name,
        "season": season_text,
        "home_ground": home_ground,
        "coaches": coach_names,
        "players": player_names,
        "founded": founded,
        "age_group": age_group_text,
        "training_schedule": training_schedule,
        "phone": phone_number,
        "phone_number": phone_number,
        "email": email,
        "role": role,
        "roles": roles,
        "organization": organization_name,
        "created_at": row.get("created_at"),
    }


async def _fetch_team_season(db: AsyncSession, *, team_id: UUID) -> str | None:
    """Return the team season when the column exists."""
    season_exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'teams'
                  AND column_name = 'season'
            )
            """
        )
    )
    if not season_exists:
        return None

    value = await db.scalar(
        text("SELECT season FROM teams WHERE id = :team_id"),
        {"team_id": team_id},
    )
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


async def _load_team_details(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
    organization_name: str,
    message: str,
) -> dict[str, Any]:
    """Load and shape one team for the Team Details screen."""
    row = await org_admin_team_service._fetch_team_row(db, team_id=team_id, org_id=org_id)
    if row is None:
        raise AppException(
            code="TEAM_NOT_FOUND",
            message="Team not found",
            status_code=404,
            details=[{"field": "team_id", "message": "Team not found"}],
        )

    season = await _fetch_team_season(db, team_id=team_id)
    if season is not None:
        row["season"] = season

    coach_names = await _fetch_team_coach_names(db, team_id=team_id, org_id=org_id)
    player_names = await _fetch_team_player_names(db, team_id=team_id, org_id=org_id)
    primary_coach = await _fetch_primary_coach(db, team_id=team_id, org_id=org_id)
    roles = await _fetch_team_roles(db, team_id=team_id, org_id=org_id)
    phone_number = await _fetch_linked_user_phone(
        db,
        email=str(primary_coach.get("email")) if primary_coach else None,
    )

    return _build_team_details_response(
        row=row,
        organization_name=organization_name,
        message=message,
        coach_names=coach_names,
        player_names=player_names,
        primary_coach=primary_coach,
        roles=roles,
        phone_number=phone_number,
    )


async def get_team(db: AsyncSession, user: User, team_id: UUID) -> dict[str, Any]:
    """Return team details for any authenticated user in the organization."""
    await org_admin_team_service._ensure_teams_table(db)
    organization = await _require_user_organization(db, user)
    logger.info("User %s loaded team details %s", user.id, team_id)
    return await _load_team_details(
        db,
        team_id=team_id,
        org_id=organization.id,
        organization_name=organization.name,
        message="Team details loaded successfully",
    )


async def create_team(
    db: AsyncSession,
    user: User,
    payload: TeamCreateRequest,
) -> dict[str, Any]:
    """Create a team for an organization admin."""
    coach_names: list[str] = getattr(payload, "coach_names", [])
    player_names: list[str] = getattr(payload, "player_names", [])
    has_email = bool(payload.email and payload.email.strip())
    has_listing_fields = bool(
        (payload.age_group and payload.age_group.strip()) and coach_names and player_names
    )

    if has_email:
        return await _create_team_with_email(db, user, payload)
    if has_listing_fields:
        return await _create_listing_team(db, user, payload)
    if payload.email is not None and not payload.email.strip():
        _validate_required_email(payload.email)
    _validate_required_age_group(payload.age_group)
    _validate_required_members(coach_names, field="coaches", label="coach")
    _validate_required_members(player_names, field="players", label="player")
    raise AppException(
        code="VALIDATION_ERROR",
        message="Team name is required",
        status_code=400,
        details=[{"field": "name", "message": "Team name is required"}],
    )


async def _create_team_with_email(
    db: AsyncSession,
    user: User,
    payload: TeamCreateRequest,
) -> dict[str, Any]:
    """Create a team with a primary coach email (Team Details flow)."""
    organization = await require_admin_organization(db, user)
    team_name = _validate_required_name(payload.name)
    email = _validate_required_email(payload.email)
    coach_names: list[str] = getattr(payload, "coach_names", [])
    player_names: list[str] = getattr(payload, "player_names", [])

    if await org_admin_team_service._duplicate_team_name_exists(
        db,
        org_id=organization.id,
        team_name=team_name,
    ):
        raise AppException(
            code="TEAM_NAME_EXISTS",
            message="A team with this name already exists",
            status_code=409,
            details=[{"field": "name", "message": "A team with this name already exists"}],
        )

    if await _email_exists_in_system(db, email=email) or await _coach_email_exists_in_org(
        db,
        org_id=organization.id,
        email=email,
    ):
        raise AppException(
            code="EMAIL_ALREADY_IN_USE",
            message="This email is already in use by another account",
            status_code=409,
            details=[{"field": "email", "message": "This email is already in use by another account"}],
        )

    team_code = _derive_team_code(team_name)
    create_payload = OrgAdminTeamCreateRequest(
        team_name=team_name,
        team_code=team_code,
        team_description=DEFAULT_DESCRIPTION,
        age_group=payload.age_group,
        coaches=[],
        phone=payload.phone,
    )
    created = await org_admin_team_service.create_org_team(db, user, create_payload)
    team_id = UUID(str(created["id"]))

    await _set_team_season(db, team_id=team_id, season=payload.season)

    coach_id = uuid4()
    first_name = "Coach"
    last_name = team_name.split()[0] if team_name.split() else "Team"
    if await client_db.table_exists(db, COACHES_TABLE):
        await db.execute(
            text("""
                INSERT INTO coaches (
                    id, org_id, team_id, first_name, last_name, email, role
                ) VALUES (
                    :id, :org_id, :team_id, :first_name, :last_name, :email, :role
                )
                """
            ),
            {
                "id": coach_id,
                "org_id": organization.id,
                "team_id": team_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "role": "head_coach",
            },
        )
        await db.commit()

    logger.info("Org admin %s created team %s via Team Details API", user.id, team_id)
    response = await _load_team_details(
        db,
        team_id=team_id,
        org_id=organization.id,
        organization_name=organization.name,
        message="Team created successfully",
    )
    if coach_names:
        response["coaches"] = coach_names
    if player_names:
        response["players"] = player_names
    response["home_ground"] = _metadata_only(payload.home_ground)
    response["training_schedule"] = _metadata_only(payload.training_schedule)
    response["founded"] = payload.founded
    response["phone"] = payload.phone or response.get("phone")
    response["email"] = email
    response["role"] = "head_coach"
    response["roles"] = ["head_coach"]
    return response


async def _create_listing_members(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    coach_names: list[str],
    player_names: list[str],
) -> None:
    """Create coach and player roster rows for a Team Listing create request."""
    if await client_db.table_exists(db, COACHES_TABLE):
        for coach_name in coach_names:
            first_name, last_name = split_full_name(coach_name)
            if not first_name:
                first_name, last_name = coach_name, "Coach"
            await db.execute(
                text("""
                    INSERT INTO coaches (
                        id, org_id, team_id, first_name, last_name, role
                    ) VALUES (
                        :id, :org_id, :team_id, :first_name, :last_name, :role
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "org_id": org_id,
                    "team_id": team_id,
                    "first_name": first_name,
                    "last_name": last_name or "Coach",
                    "role": "head_coach",
                },
            )

    if await client_db.table_exists(db, PLAYERS_TABLE):
        for player_name in player_names:
            first_name, last_name = split_full_name(player_name)
            if not first_name:
                first_name, last_name = player_name, "Player"
            await db.execute(
                text("""
                    INSERT INTO players (
                        id, org_id, team_id, first_name, last_name, active
                    ) VALUES (
                        :id, :org_id, :team_id, :first_name, :last_name, true
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "org_id": org_id,
                    "team_id": team_id,
                    "first_name": first_name,
                    "last_name": last_name or "Player",
                },
            )

    await db.commit()


async def _create_listing_team(
    db: AsyncSession,
    user: User,
    payload: TeamCreateRequest,
) -> dict[str, Any]:
    """Create a team from the Team Listing form (name, age group, coaches, players)."""
    organization = await require_admin_organization(db, user)
    team_name = _validate_required_name(payload.name)
    age_group = _validate_required_age_group(payload.age_group)
    coach_names: list[str] = getattr(payload, "coach_names", [])
    player_names: list[str] = getattr(payload, "player_names", [])
    _validate_required_members(coach_names, field="coaches", label="coach")
    _validate_required_members(player_names, field="players", label="player")

    if await org_admin_team_service._duplicate_team_name_exists(
        db,
        org_id=organization.id,
        team_name=team_name,
    ):
        raise AppException(
            code="TEAM_NAME_EXISTS",
            message="A team with this name already exists",
            status_code=409,
            details=[{"field": "name", "message": "A team with this name already exists"}],
        )

    team_code = _derive_team_code(team_name)
    create_payload = OrgAdminTeamCreateRequest(
        team_name=team_name,
        team_code=team_code,
        team_description=DEFAULT_DESCRIPTION,
        age_group=age_group,
        coaches=[],
        phone=payload.phone,
    )
    created = await org_admin_team_service.create_org_team(db, user, create_payload)
    team_id = UUID(str(created["id"]))

    await _create_listing_members(
        db,
        org_id=organization.id,
        team_id=team_id,
        coach_names=coach_names,
        player_names=player_names,
    )

    logger.info("Org admin %s created listing team %s", user.id, team_id)
    response = await _load_team_details(
        db,
        team_id=team_id,
        org_id=organization.id,
        organization_name=organization.name,
        message="Team created successfully",
    )
    response["phone"] = payload.phone
    response["age_group"] = age_group
    return response


async def _build_team_list_item(
    db: AsyncSession,
    *,
    row: dict[str, Any],
    org_id: UUID,
) -> dict[str, Any]:
    """Shape one team row for list and search responses."""
    team_id = UUID(str(row["id"]))
    coach_names = await _fetch_team_coach_names(db, team_id=team_id, org_id=org_id)
    player_names = await _fetch_team_player_names(db, team_id=team_id, org_id=org_id)
    primary_coach = await _fetch_primary_coach(db, team_id=team_id, org_id=org_id)

    age_group = row.get("level")
    age_group_text = str(age_group).strip() if age_group is not None else None
    if age_group_text == "":
        age_group_text = None

    description = row.get("description")
    description_text = str(description).strip() if description is not None else None

    email = (
        str(primary_coach.get("email")).strip()
        if primary_coach and primary_coach.get("email")
        else None
    )

    return {
        "id": team_id,
        "name": str(row["name"]),
        "age_group": age_group_text,
        "email": email,
        "status": "active",
        "coaches": coach_names,
        "players": player_names,
        "description": description_text or DEFAULT_DESCRIPTION,
    }


async def _fetch_team_rows_page(
    db: AsyncSession,
    *,
    org_id: UUID,
    page: int,
    page_size: int,
    search_query: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return a page of team rows and the total match count."""
    await org_admin_team_service._ensure_teams_table(db)

    params: dict[str, Any] = {"org_id": org_id}
    if search_query:
        params["search_term"] = f"%{search_query}%"
        count_sql = """
            SELECT COUNT(*)
            FROM teams
            WHERE org_id = :org_id
              AND name ILIKE :search_term
            """
        list_sql = """
            SELECT id, name, description, level, created_at
            FROM teams
            WHERE org_id = :org_id
              AND name ILIKE :search_term
            ORDER BY name ASC, created_at ASC
            LIMIT :limit OFFSET :offset
            """
    else:
        count_sql = """
            SELECT COUNT(*)
            FROM teams
            WHERE org_id = :org_id
            """
        list_sql = """
            SELECT id, name, description, level, created_at
            FROM teams
            WHERE org_id = :org_id
            ORDER BY name ASC, created_at ASC
            LIMIT :limit OFFSET :offset
            """

    total = await db.scalar(text(count_sql), params)

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    result = await db.execute(text(list_sql), params)
    rows = [dict(row) for row in result.mappings().all()]
    return rows, int(total or 0)


async def list_teams(
    db: AsyncSession,
    user: User,
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """Return a paginated list of teams for an organization admin."""
    organization = await require_admin_organization(db, user)
    normalized_page = _normalize_page(page)
    normalized_page_size = _normalize_page_size(page_size)

    rows, total = await _fetch_team_rows_page(
        db,
        org_id=organization.id,
        page=normalized_page,
        page_size=normalized_page_size,
    )

    items = [
        await _build_team_list_item(db, row=row, org_id=organization.id)
        for row in rows
    ]

    logger.info("Org admin %s listed %s teams (page %s)", user.id, len(items), normalized_page)
    return {
        "success": True,
        "message": "Teams loaded successfully",
        "status": "ready",
        "description": "Organization teams for the Team Listing screen",
        "link": None,
        "error": None,
        "organization": organization.name,
        "items": items,
        "pagination": build_pagination_meta(
            total=total,
            page=normalized_page,
            page_size=normalized_page_size,
        ),
    }


async def search_teams(
    db: AsyncSession,
    user: User,
    *,
    query: str,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """Search teams by name for an organization admin."""
    normalized_query = query.strip()
    if not normalized_query:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Search query is required",
            status_code=400,
            details=[{"field": "query", "message": "Search query is required"}],
        )

    organization = await require_admin_organization(db, user)
    normalized_page = _normalize_page(page)
    normalized_page_size = _normalize_page_size(page_size)

    rows, total = await _fetch_team_rows_page(
        db,
        org_id=organization.id,
        page=normalized_page,
        page_size=normalized_page_size,
        search_query=normalized_query,
    )

    items = [
        await _build_team_list_item(db, row=row, org_id=organization.id)
        for row in rows
    ]

    logger.info(
        "Org admin %s searched teams for '%s' (%s matches)",
        user.id,
        normalized_query,
        total,
    )
    return {
        "success": True,
        "message": "Teams matching your search",
        "status": "ready",
        "description": "Organization teams matching your search term",
        "link": None,
        "error": None,
        "organization": organization.name,
        "search_query": normalized_query,
        "items": items,
        "pagination": build_pagination_meta(
            total=total,
            page=normalized_page,
            page_size=normalized_page_size,
        ),
    }


async def update_team(
    db: AsyncSession,
    user: User,
    team_id: UUID,
    payload: TeamUpdateRequest,
) -> dict[str, Any]:
    """Update team and primary coach details for an organization admin."""
    organization = await require_admin_organization(db, user)
    await org_admin_team_service._ensure_teams_table(db)

    row = await org_admin_team_service._fetch_team_row(
        db,
        team_id=team_id,
        org_id=organization.id,
    )
    if row is None:
        raise AppException(
            code="TEAM_NOT_FOUND",
            message="Team not found",
            status_code=404,
            details=[{"field": "team_id", "message": "Team not found"}],
        )

    primary_coach = await _fetch_primary_coach(db, team_id=team_id, org_id=organization.id)

    update_payload = OrgAdminTeamUpdateRequest(
        team_name=payload.name,
        age_group=payload.age_group,
    )
    if payload.name is not None or payload.age_group is not None:
        await org_admin_team_service.update_org_team(db, user, team_id, update_payload)

    if payload.season is not None:
        await _set_team_season(db, team_id=team_id, season=payload.season)

    if payload.email is not None:
        normalized_email = _validate_required_email(payload.email)
        exclude_coach_id = UUID(str(primary_coach["id"])) if primary_coach else None
        if await _email_exists_in_system(db, email=normalized_email) or await _coach_email_exists_in_org(
            db,
            org_id=organization.id,
            email=normalized_email,
            exclude_coach_id=exclude_coach_id,
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

        if primary_coach is None and await client_db.table_exists(db, COACHES_TABLE):
            coach_id = uuid4()
            team_name = str(row["name"])
            await db.execute(
                text("""
                    INSERT INTO coaches (
                        id, org_id, team_id, first_name, last_name, email, role
                    ) VALUES (
                        :id, :org_id, :team_id, :first_name, :last_name, :email, :role
                    )
                    """
                ),
                {
                    "id": coach_id,
                    "org_id": organization.id,
                    "team_id": team_id,
                    "first_name": "Coach",
                    "last_name": team_name.split()[0] if team_name.split() else "Team",
                    "email": normalized_email,
                    "role": payload.role or "head_coach",
                },
            )
        elif primary_coach is not None:
            await db.execute(
                text("""
                    UPDATE coaches
                    SET email = :email
                    WHERE id = :coach_id
                      AND org_id = :org_id
                    """
                ),
                {
                    "email": normalized_email,
                    "coach_id": primary_coach["id"],
                    "org_id": organization.id,
                },
            )
        await db.commit()

    if payload.role is not None and primary_coach is not None:
        cleaned_role = payload.role.strip()
        if cleaned_role:
            await db.execute(
                text("""
                    UPDATE coaches
                    SET role = :role
                    WHERE id = :coach_id
                      AND org_id = :org_id
                    """
                ),
                {
                    "role": cleaned_role,
                    "coach_id": primary_coach["id"],
                    "org_id": organization.id,
                },
            )
            await db.commit()

    logger.info("Org admin %s updated team %s via Team Details API", user.id, team_id)
    response = await _load_team_details(
        db,
        team_id=team_id,
        org_id=organization.id,
        organization_name=organization.name,
        message="Team updated successfully",
    )
    if payload.coaches is not None:
        response["coaches"] = payload.coaches
    if payload.players is not None:
        response["players"] = payload.players
    if payload.home_ground is not None:
        response["home_ground"] = _metadata_only(payload.home_ground)
    if payload.training_schedule is not None:
        response["training_schedule"] = _metadata_only(payload.training_schedule)
    if payload.founded is not None:
        response["founded"] = payload.founded
    if payload.phone is not None:
        response["phone"] = payload.phone
    return response


async def delete_team(db: AsyncSession, user: User, team_id: UUID) -> None:
    """Delete a team for an organization admin."""
    await org_admin_team_service.delete_org_team(db, user, team_id)
    logger.info("Org admin %s deleted team %s via Team Details API", user.id, team_id)
