"""Business logic for organization admin practice plan assignments."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.practice_plan_assignment import (
    PracticePlanAssignRequest,
    PracticePlanAssignmentUpdateRequest,
)
from app.services import client_db
from app.services.org_admin_profile import require_admin_organization
from app.services.practice_plan import (
    PRACTICE_PLANS_TABLE,
    _active_column_exists,
    _active_filter_sql,
    _ensure_practice_plan_tables,
    _fetch_plan_drills,
    _plan_list_item,
)

logger = logging.getLogger(__name__)

ASSIGNMENTS_TABLE = "practice_plan_assignments"
TEAMS_TABLE = "teams"
COACHES_TABLE = "coaches"

DEFAULT_ASSIGNMENT_DESCRIPTION = "Assign practice plans to coaches and teams"


async def _ensure_assignments_table(db: AsyncSession) -> None:
    """Raise when the practice plan assignments table is unavailable."""
    if not await client_db.table_exists(db, ASSIGNMENTS_TABLE):
        raise AppException(
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Practice plan assignment operations are temporarily unavailable",
            status_code=503,
        )


async def _description_column_exists(db: AsyncSession) -> bool:
    """Return True when practice_plans.description exists."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'practice_plans'
                  AND column_name = 'description'
            )
            """
        )
    )
    return bool(exists)


def _normalize_frequency(frequency: str | None) -> str | None:
    """Return stripped frequency text or None when empty."""
    if frequency is None:
        return None
    cleaned = frequency.strip()
    return cleaned or None


def _validate_assign_request(payload: PracticePlanAssignRequest) -> PracticePlanAssignRequest:
    """Validate required assignment fields or raise 400."""
    details: list[dict[str, str]] = []
    if payload.coach_id is None:
        details.append({"field": "coach_id", "message": "Coach is required"})
    if payload.plan_id is None:
        details.append({"field": "plan_id", "message": "Practice plan is required"})
    if payload.start_date is None:
        details.append({"field": "start_date", "message": "Start date is required"})
    if details:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            status_code=400,
            details=details,
        )
    return payload


def _coach_display_name(first_name: str | None, last_name: str | None) -> str:
    """Build a coach display name from roster fields."""
    parts = [str(first_name or "").strip(), str(last_name or "").strip()]
    name = " ".join(part for part in parts if part).strip()
    return name or "Coach"


async def _validate_plan_in_org(db: AsyncSession, *, org_id: UUID, plan_id: UUID) -> dict[str, Any]:
    """Return the practice plan row when it belongs to the organization."""
    await _ensure_practice_plan_tables(db)
    active_column_exists = await _active_column_exists(db)
    description_exists = await _description_column_exists(db)
    active_sql = _active_filter_sql(active_column_exists)
    description_select = "pp.description" if description_exists else "NULL AS description"

    result = await db.execute(
        text(
            f"""
            SELECT
                pp.id,
                pp.name,
                {description_select},
                pp.created_by_name,
                pp.drill_count,
                pp.created_at
            FROM {PRACTICE_PLANS_TABLE} pp
            WHERE pp.id = :plan_id
              AND pp.org_id = :org_id
              {active_sql}
            LIMIT 1
            """
        ),
        {"plan_id": plan_id, "org_id": org_id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="PRACTICE_PLAN_NOT_FOUND",
            message="Practice plan not found",
            status_code=404,
            details=[{"field": "plan_id", "message": "Practice plan not found in this organization"}],
        )
    return dict(row)


async def _validate_coach_in_org(db: AsyncSession, *, org_id: UUID, coach_id: UUID) -> dict[str, Any]:
    """Return the coach row when it belongs to the organization."""
    if not await client_db.table_exists(db, COACHES_TABLE):
        raise AppException(
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Coach assignment is temporarily unavailable",
            status_code=503,
        )

    result = await db.execute(
        text(
            """
            SELECT id, first_name, last_name
            FROM coaches
            WHERE id = :coach_id
              AND org_id = :org_id
            LIMIT 1
            """
        ),
        {"coach_id": coach_id, "org_id": org_id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="COACH_NOT_FOUND",
            message="Coach not found",
            status_code=400,
            details=[{"field": "coach_id", "message": "Coach was not found in this organization"}],
        )
    return dict(row)


async def _validate_team_in_org(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID | None,
) -> dict[str, Any] | None:
    """Return the team row when provided and valid for the organization."""
    if team_id is None:
        return None

    if not await client_db.table_exists(db, TEAMS_TABLE):
        raise AppException(
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Team assignment is temporarily unavailable",
            status_code=503,
        )

    result = await db.execute(
        text(
            """
            SELECT id, name
            FROM teams
            WHERE id = :team_id
              AND org_id = :org_id
            LIMIT 1
            """
        ),
        {"team_id": team_id, "org_id": org_id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="TEAM_NOT_FOUND",
            message="Team not found",
            status_code=400,
            details=[{"field": "team_id", "message": "Team was not found in this organization"}],
        )
    return dict(row)


async def _duplicate_assignment_exists(
    db: AsyncSession,
    *,
    org_id: UUID,
    plan_id: UUID,
    coach_id: UUID,
    exclude_assignment_id: UUID | None = None,
) -> bool:
    """Return True when the plan is already assigned to the coach."""
    params: dict[str, Any] = {
        "org_id": org_id,
        "plan_id": plan_id,
        "coach_id": coach_id,
    }
    exclude_sql = ""
    if exclude_assignment_id is not None:
        exclude_sql = "AND id <> :exclude_assignment_id"
        params["exclude_assignment_id"] = exclude_assignment_id

    exists = await db.scalar(
        text(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM {ASSIGNMENTS_TABLE}
                WHERE org_id = :org_id
                  AND plan_id = :plan_id
                  AND coach_id = :coach_id
                  AND active = true
                  {exclude_sql}
            )
            """
        ),
        params,
    )
    return bool(exists)


async def _fetch_assignment_row(
    db: AsyncSession,
    *,
    assignment_id: UUID,
    org_id: UUID,
) -> dict[str, Any] | None:
    """Load one active assignment scoped to the organization."""
    result = await db.execute(
        text(
            f"""
            SELECT
                id,
                org_id,
                plan_id,
                coach_id,
                team_id,
                start_date,
                frequency,
                created_at
            FROM {ASSIGNMENTS_TABLE}
            WHERE id = :assignment_id
              AND org_id = :org_id
              AND active = true
            LIMIT 1
            """
        ),
        {"assignment_id": assignment_id, "org_id": org_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _assignment_to_response(
    db: AsyncSession,
    *,
    assignment: dict[str, Any],
    organization_name: str,
    message: str,
) -> dict[str, Any]:
    """Build a practice plan assignment API payload."""
    plan = await _validate_plan_in_org(
        db,
        org_id=UUID(str(assignment["org_id"])),
        plan_id=UUID(str(assignment["plan_id"])),
    )
    coach = await _validate_coach_in_org(
        db,
        org_id=UUID(str(assignment["org_id"])),
        coach_id=UUID(str(assignment["coach_id"])),
    )
    team = await _validate_team_in_org(
        db,
        org_id=UUID(str(assignment["org_id"])),
        team_id=UUID(str(assignment["team_id"])) if assignment.get("team_id") else None,
    )

    plan_description = plan.get("description")
    if plan_description is not None:
        plan_description = str(plan_description).strip() or None

    drill_count = int(plan.get("drill_count") or 0)
    plan_name = str(plan["name"])

    return {
        "success": True,
        "message": message,
        "status": "assigned",
        "description": plan_description or DEFAULT_ASSIGNMENT_DESCRIPTION,
        "link": None,
        "error": None,
        "id": assignment["id"],
        "title": plan_name,
        "name": plan_name,
        "image": None,
        "organization": organization_name,
        "plan_id": assignment["plan_id"],
        "coach_id": assignment["coach_id"],
        "coach_name": _coach_display_name(coach.get("first_name"), coach.get("last_name")),
        "team_id": assignment.get("team_id"),
        "team_name": str(team["name"]) if team is not None else None,
        "start_date": assignment["start_date"],
        "frequency": assignment.get("frequency"),
        "drill_count": drill_count,
    }


async def _assignment_list_item(
    db: AsyncSession,
    *,
    assignment: dict[str, Any],
    organization_name: str,
) -> dict[str, Any]:
    """Build one assignment list item with hero-card fields."""
    payload = await _assignment_to_response(
        db,
        assignment=assignment,
        organization_name=organization_name,
        message="Practice plan assignment loaded",
    )
    return {
        "id": payload["id"],
        "plan_id": payload["plan_id"],
        "title": payload["title"],
        "name": payload["name"],
        "description": payload["description"],
        "image": payload["image"],
        "status": payload["status"],
        "drill_count": payload["drill_count"],
        "coach_id": payload["coach_id"],
        "coach_name": payload["coach_name"],
        "team_id": payload["team_id"],
        "team_name": payload["team_name"],
        "start_date": payload["start_date"],
        "frequency": payload["frequency"],
        "organization": organization_name,
        "created_at": assignment.get("created_at"),
    }


async def list_org_practice_plan_assignments(
    db: AsyncSession,
    user: User,
) -> dict[str, Any]:
    """Return available plans and active assignments for the organization admin."""
    await _ensure_practice_plan_tables(db)
    await _ensure_assignments_table(db)
    organization = await require_admin_organization(db, user)

    active_column_exists = await _active_column_exists(db)
    description_exists = await _description_column_exists(db)
    active_sql = _active_filter_sql(active_column_exists)
    description_select = "pp.description" if description_exists else "NULL AS description"

    plan_result = await db.execute(
        text(
            f"""
            SELECT
                pp.id,
                pp.name,
                {description_select},
                pp.created_by_name,
                pp.drill_count,
                pp.created_at
            FROM {PRACTICE_PLANS_TABLE} pp
            WHERE pp.org_id = :org_id
              {active_sql}
            ORDER BY pp.created_at DESC
            """
        ),
        {"org_id": organization.id},
    )
    plan_rows = [dict(row) for row in plan_result.mappings().all()]

    plans: list[dict[str, Any]] = []
    for row in plan_rows:
        drills = await _fetch_plan_drills(db, UUID(str(row["id"])))
        plans.append(
            _plan_list_item(
                row,
                drills,
                fallback_coach_name=str(row.get("created_by_name") or "Organization Admin"),
            )
        )

    assignment_result = await db.execute(
        text(
            f"""
            SELECT
                id,
                org_id,
                plan_id,
                coach_id,
                team_id,
                start_date,
                frequency,
                created_at
            FROM {ASSIGNMENTS_TABLE}
            WHERE org_id = :org_id
              AND active = true
            ORDER BY created_at DESC
            """
        ),
        {"org_id": organization.id},
    )
    assignment_rows = [dict(row) for row in assignment_result.mappings().all()]

    assignments: list[dict[str, Any]] = []
    for row in assignment_rows:
        assignments.append(
            await _assignment_list_item(
                db,
                assignment=row,
                organization_name=organization.name,
            )
        )

    return {
        "success": True,
        "message": "Practice plans loaded successfully",
        "status": "ready",
        "description": DEFAULT_ASSIGNMENT_DESCRIPTION,
        "link": None,
        "error": None,
        "organization": organization.name,
        "plans": plans,
        "assignments": assignments,
    }


async def assign_practice_plan(
    db: AsyncSession,
    user: User,
    payload: PracticePlanAssignRequest,
) -> dict[str, Any]:
    """Assign a practice plan to a coach (and optional team) in the organization."""
    await _ensure_assignments_table(db)
    organization = await require_admin_organization(db, user)
    payload = _validate_assign_request(payload)

    assert payload.coach_id is not None
    assert payload.plan_id is not None
    assert payload.start_date is not None

    await _validate_plan_in_org(db, org_id=organization.id, plan_id=payload.plan_id)
    await _validate_coach_in_org(db, org_id=organization.id, coach_id=payload.coach_id)
    await _validate_team_in_org(db, org_id=organization.id, team_id=payload.team_id)

    if await _duplicate_assignment_exists(
        db,
        org_id=organization.id,
        plan_id=payload.plan_id,
        coach_id=payload.coach_id,
    ):
        raise AppException(
            code="PRACTICE_PLAN_ALREADY_ASSIGNED",
            message="This practice plan is already assigned to the selected coach",
            status_code=409,
            details=[
                {
                    "field": "coach_id",
                    "message": "This practice plan is already assigned to the selected coach",
                }
            ],
        )

    assignment_id = uuid4()
    frequency = _normalize_frequency(payload.frequency)

    try:
        await db.execute(
            text(
                f"""
                INSERT INTO {ASSIGNMENTS_TABLE} (
                    id, org_id, plan_id, coach_id, team_id, start_date, frequency, active
                ) VALUES (
                    :id, :org_id, :plan_id, :coach_id, :team_id, :start_date, :frequency, true
                )
                """
            ),
            {
                "id": assignment_id,
                "org_id": organization.id,
                "plan_id": payload.plan_id,
                "coach_id": payload.coach_id,
                "team_id": payload.team_id,
                "start_date": payload.start_date,
                "frequency": frequency,
            },
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Failed to assign practice plan: %s", exc)
        if "unique" in str(exc).lower():
            raise AppException(
                code="PRACTICE_PLAN_ALREADY_ASSIGNED",
                message="This practice plan is already assigned to the selected coach",
                status_code=409,
                details=[
                    {
                        "field": "coach_id",
                        "message": "This practice plan is already assigned to the selected coach",
                    }
                ],
            ) from exc
        raise AppException(
            code="PRACTICE_PLAN_ASSIGN_FAILED",
            message="Unable to assign practice plan",
            status_code=400,
        ) from exc

    row = await _fetch_assignment_row(db, assignment_id=assignment_id, org_id=organization.id)
    assert row is not None
    logger.info("Org admin %s assigned practice plan %s to coach %s", user.id, payload.plan_id, payload.coach_id)
    return await _assignment_to_response(
        db,
        assignment=row,
        organization_name=organization.name,
        message="Practice plan assigned successfully",
    )


async def update_practice_plan_assignment(
    db: AsyncSession,
    user: User,
    assignment_id: UUID,
    payload: PracticePlanAssignmentUpdateRequest,
) -> dict[str, Any]:
    """Update an existing practice plan assignment in the organization."""
    await _ensure_assignments_table(db)
    organization = await require_admin_organization(db, user)

    if (
        payload.coach_id is None
        and payload.team_id is None
        and payload.plan_id is None
        and payload.start_date is None
        and payload.frequency is None
    ):
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one field must be provided to update an assignment",
            status_code=400,
            details=[
                {
                    "field": "start_date",
                    "message": "Provide coach_id, team_id, plan_id, start_date, and/or frequency",
                }
            ],
        )

    row = await _fetch_assignment_row(db, assignment_id=assignment_id, org_id=organization.id)
    if row is None:
        raise AppException(
            code="PRACTICE_PLAN_ASSIGNMENT_NOT_FOUND",
            message="Assigned practice plan not found",
            status_code=404,
        )

    new_plan_id = UUID(str(payload.plan_id)) if payload.plan_id is not None else UUID(str(row["plan_id"]))
    new_coach_id = UUID(str(payload.coach_id)) if payload.coach_id is not None else UUID(str(row["coach_id"]))
    new_team_id = payload.team_id if payload.team_id is not None else row.get("team_id")
    if new_team_id is not None:
        new_team_id = UUID(str(new_team_id))
    new_start_date = payload.start_date if payload.start_date is not None else row["start_date"]
    new_frequency = (
        _normalize_frequency(payload.frequency)
        if payload.frequency is not None
        else row.get("frequency")
    )

    await _validate_plan_in_org(db, org_id=organization.id, plan_id=new_plan_id)
    await _validate_coach_in_org(db, org_id=organization.id, coach_id=new_coach_id)
    await _validate_team_in_org(db, org_id=organization.id, team_id=new_team_id)

    if await _duplicate_assignment_exists(
        db,
        org_id=organization.id,
        plan_id=new_plan_id,
        coach_id=new_coach_id,
        exclude_assignment_id=assignment_id,
    ):
        raise AppException(
            code="PRACTICE_PLAN_ALREADY_ASSIGNED",
            message="This practice plan is already assigned to the selected coach",
            status_code=409,
            details=[
                {
                    "field": "coach_id",
                    "message": "This practice plan is already assigned to the selected coach",
                }
            ],
        )

    try:
        await db.execute(
            text(
                f"""
                UPDATE {ASSIGNMENTS_TABLE}
                SET plan_id = :plan_id,
                    coach_id = :coach_id,
                    team_id = :team_id,
                    start_date = :start_date,
                    frequency = :frequency,
                    updated_at = NOW()
                WHERE id = :assignment_id
                  AND org_id = :org_id
                """
            ),
            {
                "assignment_id": assignment_id,
                "org_id": organization.id,
                "plan_id": new_plan_id,
                "coach_id": new_coach_id,
                "team_id": new_team_id,
                "start_date": new_start_date,
                "frequency": new_frequency,
            },
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Failed to update practice plan assignment %s: %s", assignment_id, exc)
        if "unique" in str(exc).lower():
            raise AppException(
                code="PRACTICE_PLAN_ALREADY_ASSIGNED",
                message="This practice plan is already assigned to the selected coach",
                status_code=409,
            ) from exc
        raise AppException(
            code="PRACTICE_PLAN_ASSIGN_UPDATE_FAILED",
            message="Unable to update practice plan assignment",
            status_code=400,
        ) from exc

    updated = await _fetch_assignment_row(db, assignment_id=assignment_id, org_id=organization.id)
    assert updated is not None
    logger.info("Org admin %s updated practice plan assignment %s", user.id, assignment_id)
    return await _assignment_to_response(
        db,
        assignment=updated,
        organization_name=organization.name,
        message="Practice plan assignment updated successfully",
    )


async def delete_practice_plan_assignment(
    db: AsyncSession,
    user: User,
    assignment_id: UUID,
) -> None:
    """Soft-delete a practice plan assignment in the organization."""
    await _ensure_assignments_table(db)
    organization = await require_admin_organization(db, user)

    row = await _fetch_assignment_row(db, assignment_id=assignment_id, org_id=organization.id)
    if row is None:
        raise AppException(
            code="PRACTICE_PLAN_ASSIGNMENT_NOT_FOUND",
            message="Assigned practice plan not found",
            status_code=404,
        )

    await db.execute(
        text(
            f"""
            UPDATE {ASSIGNMENTS_TABLE}
            SET active = false, updated_at = NOW()
            WHERE id = :assignment_id
              AND org_id = :org_id
            """
        ),
        {"assignment_id": assignment_id, "org_id": organization.id},
    )
    await db.commit()
    logger.info("Org admin %s deleted practice plan assignment %s", user.id, assignment_id)
