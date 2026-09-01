"""Business logic for organization admin team CRUD."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.org_admin_team import (
    OrgAdminTeamCoachInput,
    OrgAdminTeamCreateRequest,
    OrgAdminTeamUpdateRequest,
)
from app.services import client_db
from app.services.org_admin_profile import require_admin_organization

logger = logging.getLogger(__name__)

TEAMS_TABLE = "teams"
COACHES_TABLE = "coaches"
PLAYERS_TABLE = "players"

DEFAULT_TEAM_DESCRIPTION = "Team Details"


async def _ensure_teams_table(db: AsyncSession) -> None:
    """Raise when the client teams table is unavailable."""
    if not await client_db.table_exists(db, TEAMS_TABLE):
        raise AppException(
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Team operations are temporarily unavailable",
            status_code=503,
        )


async def _description_column_exists(db: AsyncSession) -> bool:
    """Return True when teams.description exists."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'teams'
                  AND column_name = 'description'
            )
            """
        )
    )
    return bool(exists)


async def _team_view_code_column_exists(db: AsyncSession) -> bool:
    """Return True when teams.team_view_code exists."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'teams'
                  AND column_name = 'team_view_code'
            )
            """
        )
    )
    return bool(exists)


async def _level_column_exists(db: AsyncSession) -> bool:
    """Return True when teams.level exists."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'teams'
                  AND column_name = 'level'
            )
            """
        )
    )
    return bool(exists)


def _validate_team_name(team_name: str | None) -> str:
    """Return a trimmed team name or raise 400 when empty."""
    cleaned = (team_name or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Team name is required",
            status_code=400,
            details=[{"field": "team_name", "message": "Team name is required"}],
        )
    return cleaned


def _validate_team_code(team_code: str | None) -> str:
    """Return a trimmed team code or raise 400 when empty."""
    cleaned = (team_code or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Team code is required",
            status_code=400,
            details=[{"field": "team_code", "message": "Team code is required"}],
        )
    return cleaned


def _normalize_team_description(description: str | None) -> str | None:
    """Return stripped team description text or None when empty."""
    if description is None:
        return None
    cleaned = description.strip()
    return cleaned or None


def _normalize_age_group(age_group: str | None) -> str | None:
    """Return stripped age group text or None when empty."""
    if age_group is None:
        return None
    cleaned = age_group.strip()
    return cleaned or None


async def _duplicate_team_name_exists(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_name: str,
    exclude_team_id: UUID | None = None,
) -> bool:
    """Return True when another team in the org already uses the display name."""
    params: dict[str, Any] = {
        "org_id": org_id,
        "team_name": team_name.strip().lower(),
    }
    exclude_sql = ""
    if exclude_team_id is not None:
        exclude_sql = "AND id <> :exclude_team_id"
        params["exclude_team_id"] = exclude_team_id

    exists = await db.scalar(
        text(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM {TEAMS_TABLE}
                WHERE org_id = :org_id
                  AND LOWER(TRIM(name)) = :team_name
                  {exclude_sql}
            )
            """
        ),
        params,
    )
    return bool(exists)


async def _duplicate_team_code_exists(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_code: str,
    exclude_team_id: UUID | None = None,
) -> bool:
    """Return True when another team in the org already uses the code."""
    if not await _team_view_code_column_exists(db):
        return False

    params: dict[str, Any] = {
        "org_id": org_id,
        "team_code": team_code.strip().lower(),
    }
    exclude_sql = ""
    if exclude_team_id is not None:
        exclude_sql = "AND id <> :exclude_team_id"
        params["exclude_team_id"] = exclude_team_id

    exists = await db.scalar(
        text(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM {TEAMS_TABLE}
                WHERE org_id = :org_id
                  AND LOWER(TRIM(team_view_code)) = :team_code
                  {exclude_sql}
            )
            """
        ),
        params,
    )
    return bool(exists)


async def _fetch_team_row(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
) -> dict[str, Any] | None:
    """Load one team row scoped to the organization."""
    description_exists = await _description_column_exists(db)
    code_exists = await _team_view_code_column_exists(db)
    level_exists = await _level_column_exists(db)

    description_select = "description" if description_exists else "NULL AS description"
    code_select = "team_view_code" if code_exists else "NULL AS team_view_code"
    level_select = "level" if level_exists else "NULL AS level"

    result = await db.execute(
        text(
            f"""
            SELECT
                id,
                name,
                {description_select},
                {code_select},
                {level_select},
                created_at
            FROM {TEAMS_TABLE}
            WHERE id = :team_id
              AND org_id = :org_id
            LIMIT 1
            """
        ),
        {"team_id": team_id, "org_id": org_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _fetch_team_coaches(db: AsyncSession, *, team_id: UUID, org_id: UUID) -> list[dict[str, Any]]:
    """Load coaches assigned to a team."""
    if not await client_db.table_exists(db, COACHES_TABLE):
        return []

    result = await db.execute(
        text(
            """
            SELECT
                id,
                first_name,
                last_name
            FROM coaches
            WHERE team_id = :team_id
              AND org_id = :org_id
            ORDER BY last_name ASC, first_name ASC
            """
        ),
        {"team_id": team_id, "org_id": org_id},
    )

    coaches: list[dict[str, Any]] = []
    for row in result.mappings().all():
        first_name = str(row.get("first_name") or "").strip()
        last_name = str(row.get("last_name") or "").strip()
        display_name = " ".join(part for part in (first_name, last_name) if part).strip()
        coaches.append(
            {
                "id": row["id"],
                "name": display_name or "Coach",
            }
        )
    return coaches


async def _validate_coach_assignments(
    db: AsyncSession,
    *,
    org_id: UUID,
    coaches: list[OrgAdminTeamCoachInput],
) -> None:
    """Ensure every assigned coach exists in the organization."""
    if not coaches:
        return

    if not await client_db.table_exists(db, COACHES_TABLE):
        raise AppException(
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Coach assignment is temporarily unavailable",
            status_code=503,
        )

    details: list[dict[str, str]] = []
    for index, coach in enumerate(coaches):
        exists = await db.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM coaches
                    WHERE id = :coach_id
                      AND org_id = :org_id
                )
                """
            ),
            {"coach_id": coach.id, "org_id": org_id},
        )
        if not exists:
            details.append(
                {
                    "field": f"coaches[{index}].id",
                    "message": "Coach was not found in this organization",
                }
            )

    if details:
        raise AppException(
            code="COACH_NOT_FOUND",
            message="One or more assigned coaches were not found",
            status_code=400,
            details=details,
        )


async def _assign_team_coaches(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    coaches: list[OrgAdminTeamCoachInput],
) -> list[dict[str, Any]]:
    """Replace coach assignments for a team and return assigned coach payloads."""
    if not await client_db.table_exists(db, COACHES_TABLE):
        return []

    await db.execute(
        text(
            """
            UPDATE coaches
            SET team_id = NULL
            WHERE org_id = :org_id
              AND team_id = :team_id
            """
        ),
        {"org_id": org_id, "team_id": team_id},
    )

    assigned: list[dict[str, Any]] = []
    for coach in coaches:
        await db.execute(
            text(
                """
                UPDATE coaches
                SET team_id = :team_id
                WHERE id = :coach_id
                  AND org_id = :org_id
                """
            ),
            {"team_id": team_id, "coach_id": coach.id, "org_id": org_id},
        )
        assigned.append({"id": coach.id, "name": coach.name.strip() or "Coach"})

    return assigned


def _team_to_response(
    row: dict[str, Any],
    coaches: list[dict[str, Any]],
    *,
    organization_name: str,
    message: str,
    ui_description: str | None,
) -> dict[str, Any]:
    """Map DB rows to the org-admin team API envelope."""
    team_description = row.get("description")
    if team_description is not None:
        team_description = str(team_description).strip() or None

    team_code = row.get("team_view_code")
    team_code_text = str(team_code).strip() if team_code is not None else ""

    age_group = row.get("level")
    age_group_text = str(age_group).strip() if age_group is not None else None
    if age_group_text == "":
        age_group_text = None

    team_name = str(row["name"])

    return {
        "success": True,
        "message": message,
        "status": "active",
        "description": ui_description or team_description or DEFAULT_TEAM_DESCRIPTION,
        "link": None,
        "error": None,
        "id": row["id"],
        "name": team_name,
        "full_name": team_name,
        "code": team_code_text,
        "organization": organization_name,
        "team_name": team_name,
        "team_code": team_code_text,
        "team_description": team_description,
        "age_group": age_group_text,
        "coaches": coaches,
        "created_at": row.get("created_at"),
    }


async def create_org_team(
    db: AsyncSession,
    user: User,
    payload: OrgAdminTeamCreateRequest,
) -> dict[str, Any]:
    """Create a team for the organization admin's organization."""
    await _ensure_teams_table(db)
    organization = await require_admin_organization(db, user)

    team_name = _validate_team_name(payload.team_name)
    team_code = _validate_team_code(payload.team_code)
    team_description = _normalize_team_description(payload.team_description)
    age_group = _normalize_age_group(payload.age_group)

    if await _duplicate_team_name_exists(db, org_id=organization.id, team_name=team_name):
        raise AppException(
            code="TEAM_NAME_EXISTS",
            message="A team with this name already exists",
            status_code=409,
            details=[{"field": "team_name", "message": "A team with this name already exists"}],
        )

    if await _duplicate_team_code_exists(db, org_id=organization.id, team_code=team_code):
        raise AppException(
            code="TEAM_CODE_EXISTS",
            message="A team with this code already exists",
            status_code=409,
            details=[{"field": "team_code", "message": "A team with this code already exists"}],
        )

    await _validate_coach_assignments(db, org_id=organization.id, coaches=payload.coaches)

    team_id = uuid4()
    description_exists = await _description_column_exists(db)
    code_exists = await _team_view_code_column_exists(db)
    level_exists = await _level_column_exists(db)

    columns = ["id", "org_id", "name", "created_at"]
    values = [":id", ":org_id", ":name", "NOW()"]
    params: dict[str, Any] = {
        "id": team_id,
        "org_id": organization.id,
        "name": team_name,
    }

    if description_exists:
        columns.append("description")
        values.append(":description")
        params["description"] = team_description

    if code_exists:
        columns.append("team_view_code")
        values.append(":team_view_code")
        params["team_view_code"] = team_code

    if level_exists:
        columns.append("level")
        values.append(":level")
        params["level"] = age_group

    insert_sql = (
        f"INSERT INTO {TEAMS_TABLE} ({', '.join(columns)}) "
        f"VALUES ({', '.join(values)})"
    )

    try:
        await db.execute(text(insert_sql), params)
        assigned_coaches = await _assign_team_coaches(
            db,
            org_id=organization.id,
            team_id=team_id,
            coaches=payload.coaches,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Failed to create org-admin team: %s", exc)
        if "team_view_code" in str(exc).lower() or "unique" in str(exc).lower():
            raise AppException(
                code="TEAM_CODE_EXISTS",
                message="A team with this code already exists",
                status_code=409,
                details=[{"field": "team_code", "message": "A team with this code already exists"}],
            ) from exc
        raise AppException(
            code="TEAM_CREATE_FAILED",
            message="Unable to create team",
            status_code=400,
        ) from exc

    row = await _fetch_team_row(db, team_id=team_id, org_id=organization.id)
    assert row is not None
    logger.info("Org admin %s created team %s", user.id, team_id)
    return _team_to_response(
        row,
        assigned_coaches,
        organization_name=organization.name,
        message="Team created successfully",
        ui_description=team_description or "Your team is ready to manage",
    )


async def get_org_team(db: AsyncSession, user: User, team_id: UUID) -> dict[str, Any]:
    """Return one team in the organization admin's organization."""
    await _ensure_teams_table(db)
    organization = await require_admin_organization(db, user)

    row = await _fetch_team_row(db, team_id=team_id, org_id=organization.id)
    if row is None:
        raise AppException(
            code="TEAM_NOT_FOUND",
            message="Team not found",
            status_code=404,
        )

    coaches = await _fetch_team_coaches(db, team_id=team_id, org_id=organization.id)
    return _team_to_response(
        row,
        coaches,
        organization_name=organization.name,
        message="Team loaded successfully",
        ui_description=row.get("description") or DEFAULT_TEAM_DESCRIPTION,
    )


async def update_org_team(
    db: AsyncSession,
    user: User,
    team_id: UUID,
    payload: OrgAdminTeamUpdateRequest,
) -> dict[str, Any]:
    """Update an existing team in the organization admin's organization."""
    await _ensure_teams_table(db)
    organization = await require_admin_organization(db, user)

    if (
        payload.team_name is None
        and payload.full_name is None
        and payload.name is None
        and payload.team_code is None
        and payload.team_description is None
        and payload.description is None
        and payload.age_group is None
        and payload.coaches is None
    ):
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one field must be provided to update a team",
            status_code=400,
            details=[
                {
                    "field": "full_name",
                    "message": (
                        "Provide full_name, description, team_name, team_code, "
                        "team_description, age_group, and/or coaches"
                    ),
                }
            ],
        )

    row = await _fetch_team_row(db, team_id=team_id, org_id=organization.id)
    if row is None:
        raise AppException(
            code="TEAM_NOT_FOUND",
            message="Team not found",
            status_code=404,
        )

    new_name = (
        _validate_team_name(payload.team_name)
        if payload.team_name is not None
        else str(row["name"])
    )
    current_code = row.get("team_view_code")
    current_code_text = str(current_code).strip() if current_code is not None else ""
    new_code = (
        _validate_team_code(payload.team_code)
        if payload.team_code is not None
        else current_code_text
    )
    new_description = (
        _normalize_team_description(payload.team_description)
        if payload.team_description is not None
        else row.get("description")
    )
    current_age_group = row.get("level")
    current_age_group_text = (
        str(current_age_group).strip() if current_age_group is not None else None
    )
    new_age_group = (
        _normalize_age_group(payload.age_group)
        if payload.age_group is not None
        else current_age_group_text
    )

    name_is_changing = (
        payload.team_name is not None or payload.full_name is not None or payload.name is not None
    )
    if name_is_changing and await _duplicate_team_name_exists(
        db,
        org_id=organization.id,
        team_name=new_name,
        exclude_team_id=team_id,
    ):
        raise AppException(
            code="TEAM_NAME_EXISTS",
            message="A team with this name already exists",
            status_code=409,
            details=[{"field": "team_name", "message": "A team with this name already exists"}],
        )

    if payload.team_code is not None and await _duplicate_team_code_exists(
        db,
        org_id=organization.id,
        team_code=new_code,
        exclude_team_id=team_id,
    ):
        raise AppException(
            code="TEAM_CODE_EXISTS",
            message="A team with this code already exists",
            status_code=409,
            details=[{"field": "team_code", "message": "A team with this code already exists"}],
        )

    if payload.coaches is not None:
        await _validate_coach_assignments(db, org_id=organization.id, coaches=payload.coaches)

    description_exists = await _description_column_exists(db)
    code_exists = await _team_view_code_column_exists(db)
    level_exists = await _level_column_exists(db)

    try:
        if payload.team_name is not None or payload.full_name is not None or payload.name is not None:
            await db.execute(
                text(f"UPDATE {TEAMS_TABLE} SET name = :name WHERE id = :team_id"),
                {"team_id": team_id, "name": new_name},
            )

        if (
            payload.team_description is not None or payload.description is not None
        ) and description_exists:
            await db.execute(
                text(f"UPDATE {TEAMS_TABLE} SET description = :description WHERE id = :team_id"),
                {"team_id": team_id, "description": new_description},
            )

        if payload.team_code is not None and code_exists:
            await db.execute(
                text(
                    f"UPDATE {TEAMS_TABLE} SET team_view_code = :team_view_code WHERE id = :team_id"
                ),
                {"team_id": team_id, "team_view_code": new_code},
            )

        if payload.age_group is not None and level_exists:
            await db.execute(
                text(f"UPDATE {TEAMS_TABLE} SET level = :level WHERE id = :team_id"),
                {"team_id": team_id, "level": new_age_group},
            )

        assigned_coaches: list[dict[str, Any]] | None = None
        if payload.coaches is not None:
            assigned_coaches = await _assign_team_coaches(
                db,
                org_id=organization.id,
                team_id=team_id,
                coaches=payload.coaches,
            )

        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Failed to update org-admin team %s: %s", team_id, exc)
        if "team_view_code" in str(exc).lower() or "unique" in str(exc).lower():
            raise AppException(
                code="TEAM_CODE_EXISTS",
                message="A team with this code already exists",
                status_code=409,
                details=[{"field": "team_code", "message": "A team with this code already exists"}],
            ) from exc
        raise AppException(
            code="TEAM_UPDATE_FAILED",
            message="Unable to update team",
            status_code=400,
        ) from exc

    updated = await _fetch_team_row(db, team_id=team_id, org_id=organization.id)
    assert updated is not None
    coaches = (
        assigned_coaches
        if assigned_coaches is not None
        else await _fetch_team_coaches(db, team_id=team_id, org_id=organization.id)
    )
    logger.info("Org admin %s updated team %s", user.id, team_id)
    saved_description = updated.get("description")
    saved_description_text = (
        str(saved_description).strip() if saved_description is not None else None
    )
    return _team_to_response(
        updated,
        coaches,
        organization_name=organization.name,
        message="Team updated successfully",
        ui_description=saved_description_text or DEFAULT_TEAM_DESCRIPTION,
    )


async def delete_org_team(db: AsyncSession, user: User, team_id: UUID) -> None:
    """Delete a team from the organization admin's organization."""
    await _ensure_teams_table(db)
    organization = await require_admin_organization(db, user)

    row = await _fetch_team_row(db, team_id=team_id, org_id=organization.id)
    if row is None:
        raise AppException(
            code="TEAM_NOT_FOUND",
            message="Team not found",
            status_code=404,
        )

    if await client_db.table_exists(db, PLAYERS_TABLE):
        player_count = await db.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM players
                WHERE org_id = :org_id
                  AND team_id = :team_id
                """
            ),
            {"org_id": organization.id, "team_id": team_id},
        )
        if int(player_count or 0) > 0:
            raise AppException(
                code="TEAM_HAS_PLAYERS",
                message="Remove players from this team before deleting it",
                status_code=409,
                details=[
                    {
                        "field": "team_id",
                        "message": "Remove players from this team before deleting it",
                    }
                ],
            )

    if await client_db.table_exists(db, COACHES_TABLE):
        await db.execute(
            text(
                """
                UPDATE coaches
                SET team_id = NULL
                WHERE org_id = :org_id
                  AND team_id = :team_id
                """
            ),
            {"org_id": organization.id, "team_id": team_id},
        )

    await db.execute(
        text(f"DELETE FROM {TEAMS_TABLE} WHERE id = :team_id AND org_id = :org_id"),
        {"team_id": team_id, "org_id": organization.id},
    )
    await db.commit()
    logger.info("Org admin %s deleted team %s", user.id, team_id)
