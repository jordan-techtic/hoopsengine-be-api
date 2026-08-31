"""Business logic for organization admin practice plan CRUD."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.org_admin_practice_plan import (
    OrgAdminPracticePlanCreateRequest,
    OrgAdminPracticePlanDrillInput,
    OrgAdminPracticePlanUpdateRequest,
)
from app.schemas.practice_plan import PracticePlanDrillInput
from app.services import client_db
from app.services.org_admin_profile import require_admin_organization
from app.services.practice_plan import (
    DRILLS_TABLE,
    MINUTES_PER_DRILL,
    PRACTICE_PLAN_DRILLS_TABLE,
    PRACTICE_PLANS_TABLE,
    _active_column_exists,
    _active_filter_sql,
    _ensure_practice_plan_tables,
    _plan_category,
    _validate_drills,
)

logger = logging.getLogger(__name__)

DEFAULT_PLAN_DESCRIPTION = "Plan Details"


def _admin_display_name(user: User) -> str:
    """Build the admin name stored on practice plan records."""
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(part.strip() for part in parts if part and part.strip()).strip()
    return name or (user.username or "Organization Admin")


def _validate_plan_name(name: str | None) -> str:
    """Return a trimmed plan name or raise 400 when empty."""
    cleaned = (name or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Practice plan name is required",
            status_code=400,
            details=[{"field": "name", "message": "Practice plan name is required"}],
        )
    return cleaned


def _normalize_plan_description(description: str | None) -> str | None:
    """Return stripped plan description text or None when empty."""
    if description is None:
        return None
    cleaned = description.strip()
    return cleaned or None


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


async def _plan_drill_description_column_exists(db: AsyncSession) -> bool:
    """Return True when practice_plan_drills.drill_description exists."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'practice_plan_drills'
                  AND column_name = 'drill_description'
            )
            """
        )
    )
    return bool(exists)


def _validate_org_admin_drills(
    drills: list[OrgAdminPracticePlanDrillInput] | None,
) -> list[OrgAdminPracticePlanDrillInput]:
    """Validate org-admin drill payloads or raise 400."""
    if drills is None or len(drills) == 0:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one drill is required",
            status_code=400,
            details=[{"field": "drills", "message": "At least one drill is required"}],
        )

    details: list[dict[str, str]] = []
    for index, drill in enumerate(drills):
        if not drill.drill_name.strip():
            details.append(
                {"field": f"drills[{index}].drill_name", "message": "Drill name is required"}
            )

    if details:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid practice plan drill data",
            status_code=400,
            details=details,
        )
    return drills


async def _drill_catalog_description_column_exists(db: AsyncSession) -> bool:
    """Return True when drills.description exists."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'drills'
                  AND column_name = 'description'
            )
            """
        )
    )
    return bool(exists)


async def _resolve_org_admin_drill(
    db: AsyncSession,
    drill: OrgAdminPracticePlanDrillInput,
) -> tuple[PracticePlanDrillInput, str | None]:
    """Resolve an org-admin drill payload to internal drill input and description."""
    name = drill.drill_name.strip()
    description = _normalize_plan_description(drill.drill_description)

    if await client_db.table_exists(db, DRILLS_TABLE):
        catalog_description_exists = await _drill_catalog_description_column_exists(db)
        description_select = ", description" if catalog_description_exists else ""
        result = await db.execute(
            text(
                f"""
                SELECT id, name, category{description_select}
                FROM drills
                WHERE LOWER(TRIM(name)) = LOWER(:name)
                LIMIT 1
                """
            ),
            {"name": name},
        )
        row = result.mappings().first()
        if row is not None:
            catalog_description = (
                str(row["description"]).strip()
                if catalog_description_exists and row.get("description")
                else None
            )
            resolved_description = description or catalog_description
            drill_type = str(row.get("category") or "general")
            return (
                PracticePlanDrillInput(
                    id=UUID(str(row["id"])),
                    name=str(row["name"]),
                    type=drill_type,
                ),
                resolved_description,
            )

    return (
        PracticePlanDrillInput(id=uuid4(), name=name, type="general"),
        description,
    )


async def _org_admin_drills_to_internal(
    db: AsyncSession,
    drills: list[OrgAdminPracticePlanDrillInput],
) -> tuple[list[PracticePlanDrillInput], list[str | None]]:
    """Convert org-admin drill inputs to internal drill rows and descriptions."""
    validated = _validate_org_admin_drills(drills)
    internal: list[PracticePlanDrillInput] = []
    descriptions: list[str | None] = []
    for drill in validated:
        resolved, drill_description = await _resolve_org_admin_drill(db, drill)
        internal.append(resolved)
        descriptions.append(drill_description)
    return _validate_drills(internal), descriptions


async def _duplicate_org_plan_exists(
    db: AsyncSession,
    *,
    org_id: UUID,
    name: str,
    exclude_plan_id: UUID | None = None,
) -> bool:
    """Return True when another active plan in the org shares the same name."""
    active_column_exists = await _active_column_exists(db)
    params: dict[str, Any] = {
        "org_id": org_id,
        "name": name.strip().lower(),
    }
    exclude_sql = ""
    if exclude_plan_id is not None:
        exclude_sql = "AND pp.id <> :exclude_plan_id"
        params["exclude_plan_id"] = exclude_plan_id

    active_sql = _active_filter_sql(active_column_exists)
    row = await db.execute(
        text(
            f"""
            SELECT pp.id
            FROM practice_plans pp
            WHERE pp.org_id = :org_id
              AND LOWER(TRIM(pp.name)) = :name
              {active_sql}
              {exclude_sql}
            LIMIT 1
            """
        ),
        params,
    )
    return row.scalar_one_or_none() is not None


async def _fetch_org_plan_row(
    db: AsyncSession,
    *,
    plan_id: UUID,
    org_id: UUID,
    active_only: bool = True,
) -> dict[str, Any] | None:
    """Load one practice plan row scoped to the organization."""
    active_column_exists = await _active_column_exists(db)
    description_column_exists = await _description_column_exists(db)
    active_sql = _active_filter_sql(active_column_exists) if active_only else ""
    description_select = "pp.description" if description_column_exists else "NULL AS description"

    result = await db.execute(
        text(
            f"""
            SELECT
                pp.id,
                pp.name,
                {description_select},
                pp.org_id,
                pp.created_by_user,
                pp.created_by_name,
                pp.drill_count,
                pp.created_at
            FROM practice_plans pp
            WHERE pp.id = :plan_id
              AND pp.org_id = :org_id
              {active_sql}
            LIMIT 1
            """
        ),
        {"plan_id": plan_id, "org_id": org_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _fetch_org_plan_drills(db: AsyncSession, plan_id: UUID) -> list[dict[str, Any]]:
    """Load drills associated with a practice plan for org-admin responses."""
    plan_drill_desc_exists = await _plan_drill_description_column_exists(db)
    catalog_desc_exists = await _drill_catalog_description_column_exists(db)

    if plan_drill_desc_exists and catalog_desc_exists:
        drill_description_expr = "COALESCE(ppd.drill_description, d.description)"
    elif plan_drill_desc_exists:
        drill_description_expr = "ppd.drill_description"
    elif catalog_desc_exists:
        drill_description_expr = "d.description"
    else:
        drill_description_expr = "NULL"

    if await client_db.table_exists(db, DRILLS_TABLE):
        query = f"""
            SELECT
                ppd.drill_id AS id,
                COALESCE(d.name, ppd.drill_name) AS drill_name,
                {drill_description_expr} AS drill_description,
                COALESCE(d.category, 'general') AS type,
                ppd.order_num
            FROM practice_plan_drills ppd
            LEFT JOIN drills d ON d.id = ppd.drill_id
            WHERE ppd.plan_id = :plan_id
            ORDER BY ppd.order_num ASC
        """
    else:
        standalone_desc_expr = (
            "ppd.drill_description" if plan_drill_desc_exists else "NULL"
        )
        query = f"""
            SELECT
                ppd.drill_id AS id,
                ppd.drill_name AS drill_name,
                {standalone_desc_expr} AS drill_description,
                'general' AS type,
                ppd.order_num
            FROM practice_plan_drills ppd
            WHERE ppd.plan_id = :plan_id
            ORDER BY ppd.order_num ASC
        """

    result = await db.execute(text(query), {"plan_id": plan_id})
    drills: list[dict[str, Any]] = []
    for row in result.mappings().all():
        drills.append(
            {
                "id": UUID(str(row["id"])) if row.get("id") is not None else uuid4(),
                "drill_name": str(row["drill_name"]),
                "drill_description": (
                    str(row["drill_description"]).strip()
                    if row.get("drill_description")
                    else None
                ),
                "type": str(row.get("type") or "general"),
            }
        )
    return drills


async def _insert_org_plan_drills(
    db: AsyncSession,
    *,
    plan_id: UUID,
    drills: list[PracticePlanDrillInput],
    drill_descriptions: list[str | None],
) -> list[dict[str, Any]]:
    """Replace drill rows for a plan and return org-admin drill payloads."""
    plan_drill_description_exists = await _plan_drill_description_column_exists(db)

    await db.execute(
        text("DELETE FROM practice_plan_drills WHERE plan_id = :plan_id"),
        {"plan_id": plan_id},
    )

    resolved: list[dict[str, Any]] = []
    for order_num, (drill, drill_description) in enumerate(
        zip(drills, drill_descriptions, strict=True)
    ):
        if plan_drill_description_exists:
            await db.execute(
                text(
                    """
                    INSERT INTO practice_plan_drills (
                        id, plan_id, drill_id, drill_name, drill_description, order_num
                    ) VALUES (
                        :id, :plan_id, :drill_id, :drill_name, :drill_description, :order_num
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "plan_id": plan_id,
                    "drill_id": drill.id,
                    "drill_name": drill.name,
                    "drill_description": drill_description,
                    "order_num": order_num,
                },
            )
        else:
            await db.execute(
                text(
                    """
                    INSERT INTO practice_plan_drills (
                        id, plan_id, drill_id, drill_name, order_num
                    ) VALUES (
                        :id, :plan_id, :drill_id, :drill_name, :order_num
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "plan_id": plan_id,
                    "drill_id": drill.id,
                    "drill_name": drill.name,
                    "order_num": order_num,
                },
            )

        resolved.append(
            {
                "drill_name": drill.name,
                "drill_description": drill_description,
                "type": drill.type,
            }
        )

    await db.execute(
        text(
            """
            UPDATE practice_plans
            SET drill_count = :drill_count
            WHERE id = :plan_id
            """
        ),
        {"plan_id": plan_id, "drill_count": len(resolved)},
    )
    return resolved


def _plan_duration_label(drill_count: int) -> str:
    """Estimate plan duration for Practice Plans list cards."""
    minutes = max(int(drill_count) * MINUTES_PER_DRILL, MINUTES_PER_DRILL)
    return f"{minutes} min"


def _plan_list_item(
    row: dict[str, Any],
    drills: list[dict[str, Any]],
    *,
    organization_name: str,
    fallback_creator_name: str,
) -> dict[str, Any]:
    """Build one org-admin practice plan list item."""
    drill_count = int(row.get("drill_count") or len(drills))
    plan_description = row.get("description")
    if plan_description is not None:
        plan_description = str(plan_description).strip() or None

    category_drills = [
        {"type": drill.get("type", "general")} for drill in drills if drill.get("type")
    ]
    return {
        "id": row["id"],
        "name": row["name"],
        "title": row["name"],
        "description": plan_description,
        "status": "active",
        "drill_count": drill_count,
        "duration": _plan_duration_label(drill_count),
        "category": _plan_category(category_drills),
        "created_by_name": row.get("created_by_name") or fallback_creator_name,
        "organization": organization_name,
        "drills": [
            {
                "drill_name": drill["drill_name"],
                "drill_description": drill.get("drill_description"),
            }
            for drill in drills
        ],
        "created_at": row.get("created_at"),
    }


def _plan_to_response(
    row: dict[str, Any],
    drills: list[dict[str, Any]],
    *,
    organization_name: str,
    message: str,
    ui_description: str | None,
) -> dict[str, Any]:
    """Map DB rows to the org-admin practice plan API envelope."""
    plan_description = row.get("description")
    if plan_description is not None:
        plan_description = str(plan_description).strip() or None

    return {
        "success": True,
        "message": message,
        "status": "active",
        "description": ui_description or plan_description or DEFAULT_PLAN_DESCRIPTION,
        "link": None,
        "error": None,
        "id": row["id"],
        "title": row["name"],
        "name": row["name"],
        "organization": organization_name,
        "drill_count": int(row.get("drill_count") or len(drills)),
        "created_by_name": row.get("created_by_name") or "Organization Admin",
        "drills": [
            {
                "drill_name": drill["drill_name"],
                "drill_description": drill.get("drill_description"),
            }
            for drill in drills
        ],
        "created_at": row.get("created_at"),
    }


async def create_org_practice_plan(
    db: AsyncSession,
    user: User,
    payload: OrgAdminPracticePlanCreateRequest,
) -> dict[str, Any]:
    """Create a new active practice plan for the organization admin's organization."""
    await _ensure_practice_plan_tables(db)
    organization = await require_admin_organization(db, user)

    name = _validate_plan_name(payload.name)
    plan_description = _normalize_plan_description(payload.description)
    drills, drill_descriptions = await _org_admin_drills_to_internal(db, payload.drills)

    if await _duplicate_org_plan_exists(db, org_id=organization.id, name=name):
        raise AppException(
            code="PRACTICE_PLAN_NAME_EXISTS",
            message="A practice plan with this name already exists",
            status_code=409,
            details=[{"field": "name", "message": "A practice plan with this name already exists"}],
        )

    plan_id = uuid4()
    admin_name = _admin_display_name(user)
    active_column_exists = await _active_column_exists(db)
    description_column_exists = await _description_column_exists(db)

    columns = [
        "id",
        "name",
        "org_id",
        "created_by_user",
        "created_by_name",
        "drill_count",
        "created_at",
    ]
    values = [
        ":id",
        ":name",
        ":org_id",
        ":created_by_user",
        ":created_by_name",
        ":drill_count",
        "NOW()",
    ]
    params: dict[str, Any] = {
        "id": plan_id,
        "name": name,
        "org_id": organization.id,
        "created_by_user": user.id,
        "created_by_name": admin_name,
        "drill_count": len(drills),
    }

    if description_column_exists:
        columns.append("description")
        values.append(":description")
        params["description"] = plan_description

    if active_column_exists:
        columns.append("active")
        values.append("true")

    insert_sql = (
        f"INSERT INTO {PRACTICE_PLANS_TABLE} ({', '.join(columns)}) "
        f"VALUES ({', '.join(values)})"
    )

    try:
        await db.execute(text(insert_sql), params)
        resolved_drills = await _insert_org_plan_drills(
            db,
            plan_id=plan_id,
            drills=drills,
            drill_descriptions=drill_descriptions,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Failed to create org-admin practice plan: %s", exc)
        raise AppException(
            code="PRACTICE_PLAN_CREATE_FAILED",
            message="Unable to create practice plan",
            status_code=400,
        ) from exc

    row = await _fetch_org_plan_row(db, plan_id=plan_id, org_id=organization.id)
    assert row is not None
    logger.info("Org admin %s created practice plan %s", user.id, plan_id)
    return _plan_to_response(
        row,
        resolved_drills,
        organization_name=organization.name,
        message="Practice plan created successfully",
        ui_description=plan_description or "Your active practice plan is ready to use",
    )


async def list_org_practice_plans(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return all active practice plans for the organization admin's organization."""
    await _ensure_practice_plan_tables(db)
    organization = await require_admin_organization(db, user)

    active_column_exists = await _active_column_exists(db)
    description_column_exists = await _description_column_exists(db)
    active_sql = _active_filter_sql(active_column_exists)
    description_select = "pp.description" if description_column_exists else "NULL AS description"

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
            WHERE pp.org_id = :org_id
              {active_sql}
            ORDER BY pp.created_at DESC
            """
        ),
        {"org_id": organization.id},
    )
    rows = [dict(row) for row in result.mappings().all()]

    plans: list[dict[str, Any]] = []
    for row in rows:
        drills = await _fetch_org_plan_drills(db, UUID(str(row["id"])))
        plans.append(
            _plan_list_item(
                row,
                drills,
                organization_name=organization.name,
                fallback_creator_name=_admin_display_name(user),
            )
        )

    return {
        "success": True,
        "message": "Practice plans loaded successfully",
        "status": "ready",
        "description": "Your active practice plans",
        "link": None,
        "error": None,
        "organization": organization.name,
        "plans": plans,
    }


async def update_org_practice_plan(
    db: AsyncSession,
    user: User,
    plan_id: UUID,
    payload: OrgAdminPracticePlanUpdateRequest,
) -> dict[str, Any]:
    """Update an existing practice plan in the organization admin's organization."""
    await _ensure_practice_plan_tables(db)
    organization = await require_admin_organization(db, user)

    if payload.name is None and payload.description is None and payload.drills is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one field must be provided to update a practice plan",
            status_code=400,
            details=[
                {
                    "field": "name",
                    "message": "Provide name, description, and/or drills to update the practice plan",
                }
            ],
        )

    row = await _fetch_org_plan_row(db, plan_id=plan_id, org_id=organization.id)
    if row is None:
        raise AppException(
            code="PRACTICE_PLAN_NOT_FOUND",
            message="Practice plan not found",
            status_code=404,
        )

    new_name = _validate_plan_name(payload.name) if payload.name is not None else str(row["name"])
    new_description = (
        _normalize_plan_description(payload.description)
        if payload.description is not None
        else row.get("description")
    )

    drills: list[PracticePlanDrillInput] | None = None
    drill_descriptions: list[str | None] | None = None
    if payload.drills is not None:
        drills, drill_descriptions = await _org_admin_drills_to_internal(db, payload.drills)

    if payload.name is not None and await _duplicate_org_plan_exists(
        db,
        org_id=organization.id,
        name=new_name,
        exclude_plan_id=plan_id,
    ):
        raise AppException(
            code="PRACTICE_PLAN_NAME_EXISTS",
            message="A practice plan with this name already exists",
            status_code=409,
            details=[{"field": "name", "message": "A practice plan with this name already exists"}],
        )

    description_column_exists = await _description_column_exists(db)

    try:
        if payload.name is not None:
            await db.execute(
                text("UPDATE practice_plans SET name = :name WHERE id = :plan_id"),
                {"plan_id": plan_id, "name": new_name},
            )

        if payload.description is not None and description_column_exists:
            await db.execute(
                text("UPDATE practice_plans SET description = :description WHERE id = :plan_id"),
                {"plan_id": plan_id, "description": new_description},
            )

        if drills is not None and drill_descriptions is not None:
            resolved_drills = await _insert_org_plan_drills(
                db,
                plan_id=plan_id,
                drills=drills,
                drill_descriptions=drill_descriptions,
            )
        else:
            resolved_drills = await _fetch_org_plan_drills(db, plan_id)

        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Failed to update org-admin practice plan %s: %s", plan_id, exc)
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid practice plan update data",
            status_code=400,
        ) from exc

    updated = await _fetch_org_plan_row(db, plan_id=plan_id, org_id=organization.id)
    assert updated is not None
    return _plan_to_response(
        updated,
        resolved_drills,
        organization_name=organization.name,
        message="Practice plan updated successfully",
        ui_description="Your practice plan changes have been saved",
    )


async def delete_org_practice_plan(db: AsyncSession, user: User, plan_id: UUID) -> None:
    """Soft-delete a practice plan so it no longer appears in active org listings."""
    await _ensure_practice_plan_tables(db)
    organization = await require_admin_organization(db, user)

    row = await _fetch_org_plan_row(db, plan_id=plan_id, org_id=organization.id)
    if row is None:
        raise AppException(
            code="PRACTICE_PLAN_NOT_FOUND",
            message="Practice plan not found",
            status_code=404,
        )

    active_column_exists = await _active_column_exists(db)
    if active_column_exists:
        await db.execute(
            text("UPDATE practice_plans SET active = false WHERE id = :plan_id"),
            {"plan_id": plan_id},
        )
    else:
        await db.execute(
            text(f"DELETE FROM {PRACTICE_PLAN_DRILLS_TABLE} WHERE plan_id = :plan_id"),
            {"plan_id": plan_id},
        )
        await db.execute(
            text(f"DELETE FROM {PRACTICE_PLANS_TABLE} WHERE id = :plan_id"),
            {"plan_id": plan_id},
        )

    await db.commit()
    logger.info("Org admin %s deleted practice plan %s", user.id, plan_id)
