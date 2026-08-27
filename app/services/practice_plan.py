"""Business logic for coach practice plan CRUD."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.coach_practice_plan import (
    CoachPracticePlanCreateRequest,
    CoachPracticePlanDrillInput,
    CoachPracticePlanUpdateRequest,
)
from app.schemas.practice_plan import (
    PracticePlanCreateRequest,
    PracticePlanDrillInput,
    PracticePlanUpdateRequest,
)
from app.services import client_db, coach_identity

logger = logging.getLogger(__name__)

PRACTICE_PLANS_TABLE = "practice_plans"
PRACTICE_PLAN_DRILLS_TABLE = "practice_plan_drills"
DRILLS_TABLE = "drills"
DEFAULT_PLAN_DESCRIPTION = "Plan Details"
MINUTES_PER_DRILL = 10


def _plan_duration_label(drill_count: int) -> str:
    """Estimate plan duration for Practice Plans list cards."""
    minutes = max(int(drill_count) * MINUTES_PER_DRILL, MINUTES_PER_DRILL)
    return f"{minutes} min"


def _plan_category(drills: list[dict[str, Any]]) -> str:
    """Derive a category tab label from plan drills."""
    if not drills:
        return "All"

    drill_type = str(drills[0].get("type", "general")).lower()
    if any(token in drill_type for token in ("endurance", "conditioning", "warm")):
        return "Endurance"
    if "speed" in drill_type:
        return "Speed"
    if any(token in drill_type for token in ("shooting", "dribbl", "pass", "defense", "free_throw")):
        return "Skills"
    return "Skills"


def _plan_list_item(
    row: dict[str, Any],
    drills: list[dict[str, Any]],
    *,
    fallback_coach_name: str,
) -> dict[str, Any]:
    drill_count = int(row.get("drill_count") or len(drills))
    return {
        "id": row["id"],
        "name": row["name"],
        "status": "active",
        "drill_count": drill_count,
        "duration": _plan_duration_label(drill_count),
        "category": _plan_category(drills),
        "created_by_name": row.get("created_by_name") or fallback_coach_name,
        "drills": drills,
        "created_at": row.get("created_at"),
    }


def _coach_display_name(user: User) -> str:
    """Build the coach name shown on practice plan cards."""
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(part.strip() for part in parts if part and part.strip()).strip()
    return name or (user.username or "Coach")


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


def _extract_coach_plan_name(
    *,
    plan_name: str | None = None,
    title: str | None = None,
    name: str | None = None,
    full_name: str | None = None,
) -> str:
    """Resolve plan name from coach-facing aliases."""
    for candidate in (plan_name, full_name, title, name):
        if candidate is not None and candidate.strip():
            return _validate_plan_name(candidate)

    raise AppException(
        code="VALIDATION_ERROR",
        message="Practice plan name is required",
        status_code=400,
        details=[
            {
                "field": "plan_name",
                "message": "Provide plan_name, full_name, title, or name for the practice plan",
            }
        ],
    )


def _uses_create_screen_payload(payload: PracticePlanCreateRequest) -> bool:
    """Return True when the request uses Create Practice Plan form fields."""
    return (
        payload.selected_drills is not None
        or payload.plan_name is not None
        or payload.full_name is not None
    )


async def _selected_drills_to_internal(
    db: AsyncSession,
    selected_drills: list[str],
) -> list[PracticePlanDrillInput]:
    """Convert selected drill names to internal drill inputs."""
    if not selected_drills:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one drill is required",
            status_code=400,
            details=[{"field": "selected_drills", "message": "At least one drill is required"}],
        )

    coach_drills = [
        CoachPracticePlanDrillInput(name=drill_name.strip())
        for drill_name in selected_drills
        if drill_name and drill_name.strip()
    ]
    return await _coach_drills_to_internal(db, coach_drills)


async def _resolve_create_payload(
    db: AsyncSession,
    payload: PracticePlanCreateRequest,
) -> tuple[str, list[PracticePlanDrillInput]]:
    """Normalize create payloads from Create Practice Plan or legacy formats."""
    if _uses_create_screen_payload(payload):
        plan_name = _extract_coach_plan_name(
            plan_name=payload.plan_name,
            full_name=payload.full_name,
            name=payload.name,
        )
        if payload.selected_drills is None:
            raise AppException(
                code="VALIDATION_ERROR",
                message="At least one drill is required",
                status_code=400,
                details=[
                    {
                        "field": "selected_drills",
                        "message": "Select at least one drill for the practice plan",
                    }
                ],
            )
        drills = await _selected_drills_to_internal(db, payload.selected_drills)
        return plan_name, drills

    if payload.name is None or payload.drills is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Practice plan name and drills are required",
            status_code=400,
            details=[
                {
                    "field": "plan_name",
                    "message": "Provide plan_name and selected_drills, or name and drills",
                }
            ],
        )

    return _validate_plan_name(payload.name), _validate_drills(payload.drills)


def _coach_plan_description(description: str | None) -> str:
    """Return UI-safe plan description text."""
    cleaned = (description or "").strip()
    return cleaned or DEFAULT_PLAN_DESCRIPTION


async def _resolve_coach_drill(
    db: AsyncSession,
    drill: CoachPracticePlanDrillInput,
) -> PracticePlanDrillInput:
    """Resolve a coach drill payload to the internal drill input shape."""
    name = drill.name.strip()
    if not name:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Drill name is required",
            status_code=400,
            details=[{"field": "drills[].name", "message": "Drill name is required"}],
        )

    if drill.id is not None:
        drill_type = (drill.type or "general").strip() or "general"
        return PracticePlanDrillInput(id=drill.id, name=name, type=drill_type)

    if await client_db.table_exists(db, DRILLS_TABLE):
        result = await db.execute(
            text(
                """
                SELECT id, name, category
                FROM drills
                WHERE LOWER(TRIM(name)) = LOWER(:name)
                LIMIT 1
                """
            ),
            {"name": name},
        )
        row = result.mappings().first()
        if row is not None:
            return PracticePlanDrillInput(
                id=UUID(str(row["id"])),
                name=str(row["name"]),
                type=str(row["category"]),
            )

    drill_type = (drill.type or "general").strip() or "general"
    return PracticePlanDrillInput(id=uuid4(), name=name, type=drill_type)


async def _coach_drills_to_internal(
    db: AsyncSession,
    drills: list[CoachPracticePlanDrillInput],
) -> list[PracticePlanDrillInput]:
    """Convert coach drill inputs and validate the resolved list."""
    if not drills:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one drill is required",
            status_code=400,
            details=[{"field": "drills", "message": "At least one drill is required"}],
        )

    resolved: list[PracticePlanDrillInput] = []
    details: list[dict[str, str]] = []
    for index, drill in enumerate(drills):
        try:
            resolved.append(await _resolve_coach_drill(db, drill))
        except AppException as exc:
            if exc.details and isinstance(exc.details, list):
                for item in exc.details:
                    field = str(item.get("field", "drills"))
                    if field == "drills[].name":
                        field = f"drills[{index}].name"
                    details.append({"field": field, "message": str(item.get("message", exc.message))})
            else:
                details.append({"field": f"drills[{index}]", "message": exc.message})

    if details:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid practice plan drill data",
            status_code=400,
            details=details,
        )

    return _validate_drills(resolved)


def _validate_drills(drills: list[PracticePlanDrillInput] | None) -> list[PracticePlanDrillInput]:
    """Validate drill list content or raise 400."""
    if drills is None or len(drills) == 0:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one drill is required",
            status_code=400,
            details=[{"field": "drills", "message": "At least one drill is required"}],
        )

    details: list[dict[str, str]] = []
    for index, drill in enumerate(drills):
        if not drill.name.strip():
            details.append({"field": f"drills[{index}].name", "message": "Drill name is required"})
        if not drill.type.strip():
            details.append({"field": f"drills[{index}].type", "message": "Drill type is required"})

    if details:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid practice plan drill data",
            status_code=400,
            details=details,
        )
    return drills


async def _ensure_practice_plan_tables(db: AsyncSession) -> None:
    """Require client practice plan tables before CRUD operations."""
    await client_db.require_table(db, PRACTICE_PLANS_TABLE)
    await client_db.require_table(db, PRACTICE_PLAN_DRILLS_TABLE)


async def _active_column_exists(db: AsyncSession) -> bool:
    """Return True when practice_plans.active exists."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'practice_plans'
                  AND column_name = 'active'
            )
            """
        )
    )
    return bool(exists)


def _active_filter_sql(active_column_exists: bool) -> str:
    """Build SQL predicate limiting results to active plans."""
    if active_column_exists:
        return "AND pp.active = true"
    return ""


async def _duplicate_plan_exists(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    name: str,
    exclude_plan_id: UUID | None = None,
) -> bool:
    """Return True when another active plan shares the same name for this coach."""
    active_column_exists = await _active_column_exists(db)
    params: dict[str, Any] = {
        "org_id": org_id,
        "user_id": user_id,
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
              AND pp.created_by_user = :user_id
              AND LOWER(TRIM(pp.name)) = :name
              {active_sql}
              {exclude_sql}
            LIMIT 1
            """
        ),
        params,
    )
    return row.scalar_one_or_none() is not None


async def _resolve_drill(
    db: AsyncSession,
    drill: PracticePlanDrillInput,
) -> dict[str, Any]:
    """Resolve drill metadata from the drills table when available."""
    if await client_db.table_exists(db, DRILLS_TABLE):
        result = await db.execute(
            text(
                """
                SELECT id, name, category
                FROM drills
                WHERE id = :drill_id
                LIMIT 1
                """
            ),
            {"drill_id": drill.id},
        )
        row = result.mappings().first()
        if row is not None:
            return {
                "id": UUID(str(row["id"])),
                "name": str(row["name"]),
                "type": str(row["category"]),
            }

    return {
        "id": drill.id,
        "name": drill.name.strip(),
        "type": drill.type.strip(),
    }


async def _insert_plan_drills(
    db: AsyncSession,
    *,
    plan_id: UUID,
    drills: list[PracticePlanDrillInput],
) -> list[dict[str, Any]]:
    """Replace drill rows for a plan and return resolved drill payloads."""
    await db.execute(
        text("DELETE FROM practice_plan_drills WHERE plan_id = :plan_id"),
        {"plan_id": plan_id},
    )

    resolved: list[dict[str, Any]] = []
    for order_num, drill in enumerate(drills):
        item = await _resolve_drill(db, drill)
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
                "drill_id": item["id"],
                "drill_name": item["name"],
                "order_num": order_num,
            },
        )
        resolved.append(item)

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


async def _fetch_plan_row(
    db: AsyncSession,
    *,
    plan_id: UUID,
    org_id: UUID,
    user_id: UUID,
    active_only: bool = True,
) -> dict[str, Any] | None:
    """Load one owned practice plan row."""
    active_column_exists = await _active_column_exists(db)
    active_sql = _active_filter_sql(active_column_exists) if active_only else ""

    result = await db.execute(
        text(
            f"""
            SELECT
                pp.id,
                pp.name,
                pp.org_id,
                pp.created_by_user,
                pp.created_by_name,
                pp.drill_count,
                pp.created_at
            FROM practice_plans pp
            WHERE pp.id = :plan_id
              AND pp.org_id = :org_id
              AND pp.created_by_user = :user_id
              {active_sql}
            LIMIT 1
            """
        ),
        {"plan_id": plan_id, "org_id": org_id, "user_id": user_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _fetch_plan_drills(db: AsyncSession, plan_id: UUID) -> list[dict[str, Any]]:
    """Load drills associated with a practice plan."""
    if await client_db.table_exists(db, DRILLS_TABLE):
        query = """
            SELECT
                ppd.drill_id AS id,
                COALESCE(d.name, ppd.drill_name) AS name,
                COALESCE(d.category, 'general') AS type,
                ppd.order_num
            FROM practice_plan_drills ppd
            LEFT JOIN drills d ON d.id = ppd.drill_id
            WHERE ppd.plan_id = :plan_id
            ORDER BY ppd.order_num ASC
        """
    else:
        query = """
            SELECT
                ppd.drill_id AS id,
                ppd.drill_name AS name,
                'general' AS type,
                ppd.order_num
            FROM practice_plan_drills ppd
            WHERE ppd.plan_id = :plan_id
            ORDER BY ppd.order_num ASC
        """

    result = await db.execute(text(query), {"plan_id": plan_id})
    return [
        {
            "id": UUID(str(row["id"])),
            "name": str(row["name"]),
            "type": str(row["type"]),
        }
        for row in result.mappings().all()
    ]


def _plan_to_response(
    row: dict[str, Any],
    drills: list[dict[str, Any]],
    *,
    message: str,
    description: str,
) -> dict[str, Any]:
    """Map DB rows to the practice plan API envelope."""
    return {
        "success": True,
        "message": message,
        "status": "active",
        "description": description,
        "link": None,
        "error": None,
        "id": row["id"],
        "title": row["name"],
        "name": row["name"],
        "drill_count": int(row.get("drill_count") or len(drills)),
        "created_by_name": row.get("created_by_name") or "Coach",
        "drills": drills,
        "created_at": row.get("created_at"),
    }


async def create_practice_plan(
    db: AsyncSession,
    user: User,
    payload: PracticePlanCreateRequest,
) -> dict[str, Any]:
    """Create a new active practice plan for the authenticated coach."""
    await _ensure_practice_plan_tables(db)
    context = await coach_identity.ensure_recorder_context(db, user)

    name, drills = await _resolve_create_payload(db, payload)

    if await _duplicate_plan_exists(
        db,
        org_id=context.org_id,
        user_id=user.id,
        name=name,
    ):
        raise AppException(
            code="PRACTICE_PLAN_NAME_EXISTS",
            message="A practice plan with this name already exists",
            status_code=409,
            details=[{"field": "name", "message": "A practice plan with this name already exists"}],
        )

    plan_id = uuid4()
    coach_name = _coach_display_name(user)
    active_column_exists = await _active_column_exists(db)

    insert_sql = """
        INSERT INTO practice_plans (
            id, name, org_id, created_by_user, created_by_name, drill_count, created_at
    """
    values_sql = """
        ) VALUES (
            :id, :name, :org_id, :created_by_user, :created_by_name, :drill_count, NOW()
        )
    """
    if active_column_exists:
        insert_sql = """
            INSERT INTO practice_plans (
                id, name, org_id, created_by_user, created_by_name, drill_count, created_at, active
        """
        values_sql = """
            ) VALUES (
                :id, :name, :org_id, :created_by_user, :created_by_name, :drill_count, NOW(), true
            )
        """

    try:
        await db.execute(
            text(insert_sql + values_sql),
            {
                "id": plan_id,
                "name": name,
                "org_id": context.org_id,
                "created_by_user": user.id,
                "created_by_name": coach_name,
                "drill_count": len(drills),
            },
        )
        resolved_drills = await _insert_plan_drills(db, plan_id=plan_id, drills=drills)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Failed to create practice plan: %s", exc)
        raise AppException(
            code="PRACTICE_PLAN_CREATE_FAILED",
            message="Unable to create practice plan",
            status_code=400,
        ) from exc

    row = await _fetch_plan_row(
        db,
        plan_id=plan_id,
        org_id=context.org_id,
        user_id=user.id,
    )
    assert row is not None
    logger.info("Coach %s created practice plan %s", user.id, plan_id)
    return _plan_to_response(
        row,
        resolved_drills,
        message="Practice plan created successfully",
        description="Your active practice plan is ready to use",
    )


async def list_active_practice_plans(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return active practice plans for the authenticated user's organization."""
    await _ensure_practice_plan_tables(db)

    if user.org_id is None:
        return {
            "success": True,
            "message": "Active practice plans loaded successfully",
            "status": "ready",
            "description": "Your active practice plans",
            "link": None,
            "error": None,
            "plans": [],
        }

    active_column_exists = await _active_column_exists(db)
    active_sql = _active_filter_sql(active_column_exists)

    if user.role == UserRole.COACH.value:
        owner_sql = "AND pp.created_by_user = :user_id"
        params: dict[str, Any] = {"org_id": user.org_id, "user_id": user.id}
    else:
        owner_sql = ""
        params = {"org_id": user.org_id}

    result = await db.execute(
        text(
            f"""
            SELECT
                pp.id,
                pp.name,
                pp.created_by_name,
                pp.drill_count,
                pp.created_at
            FROM practice_plans pp
            WHERE pp.org_id = :org_id
              {owner_sql}
              {active_sql}
            ORDER BY pp.created_at DESC
            """
        ),
        params,
    )
    rows = [dict(row) for row in result.mappings().all()]

    plans: list[dict[str, Any]] = []
    for row in rows:
        drills = await _fetch_plan_drills(db, UUID(str(row["id"])))
        plans.append(
            _plan_list_item(
                row,
                drills,
                fallback_coach_name=_coach_display_name(user),
            )
        )

    return {
        "success": True,
        "message": "Active practice plans loaded successfully",
        "status": "ready",
        "description": "Your active practice plans",
        "link": None,
        "error": None,
        "plans": plans,
    }


async def update_practice_plan(
    db: AsyncSession,
    user: User,
    plan_id: UUID,
    payload: PracticePlanUpdateRequest,
) -> dict[str, Any]:
    """Update an existing practice plan owned by the authenticated coach."""
    await _ensure_practice_plan_tables(db)
    context = await coach_identity.ensure_recorder_context(db, user)

    if payload.name is None and payload.drills is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one field must be provided to update a practice plan",
            status_code=400,
            details=[
                {
                    "field": "name",
                    "message": "Provide name and/or drills to update the practice plan",
                }
            ],
        )

    row = await _fetch_plan_row(
        db,
        plan_id=plan_id,
        org_id=context.org_id,
        user_id=user.id,
    )
    if row is None:
        raise AppException(
            code="PRACTICE_PLAN_NOT_FOUND",
            message="Practice plan not found",
            status_code=404,
        )

    new_name = _validate_plan_name(payload.name) if payload.name is not None else str(row["name"])
    drills = _validate_drills(payload.drills) if payload.drills is not None else None

    if payload.name is not None and await _duplicate_plan_exists(
        db,
        org_id=context.org_id,
        user_id=user.id,
        name=new_name,
        exclude_plan_id=plan_id,
    ):
        raise AppException(
            code="PRACTICE_PLAN_NAME_EXISTS",
            message="A practice plan with this name already exists",
            status_code=409,
            details=[{"field": "name", "message": "A practice plan with this name already exists"}],
        )

    try:
        if payload.name is not None:
            await db.execute(
                text(
                    """
                    UPDATE practice_plans
                    SET name = :name
                    WHERE id = :plan_id
                    """
                ),
                {"plan_id": plan_id, "name": new_name},
            )

        if drills is not None:
            resolved_drills = await _insert_plan_drills(db, plan_id=plan_id, drills=drills)
        else:
            resolved_drills = await _fetch_plan_drills(db, plan_id)

        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Failed to update practice plan %s: %s", plan_id, exc)
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid practice plan update data",
            status_code=400,
        ) from exc

    updated = await _fetch_plan_row(
        db,
        plan_id=plan_id,
        org_id=context.org_id,
        user_id=user.id,
    )
    assert updated is not None
    return _plan_to_response(
        updated,
        resolved_drills,
        message="Practice plan updated successfully",
        description="Your practice plan changes have been saved",
    )


async def delete_practice_plan(db: AsyncSession, user: User, plan_id: UUID) -> None:
    """Soft-delete a practice plan so it no longer appears in active listings."""
    await _ensure_practice_plan_tables(db)
    context = await coach_identity.ensure_recorder_context(db, user)

    row = await _fetch_plan_row(
        db,
        plan_id=plan_id,
        org_id=context.org_id,
        user_id=user.id,
    )
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
            text("DELETE FROM practice_plan_drills WHERE plan_id = :plan_id"),
            {"plan_id": plan_id},
        )
        await db.execute(
            text("DELETE FROM practice_plans WHERE id = :plan_id"),
            {"plan_id": plan_id},
        )

    await db.commit()
    logger.info("Coach %s deleted practice plan %s", user.id, plan_id)


async def get_practice_plan(db: AsyncSession, user: User, plan_id: UUID) -> dict[str, Any]:
    """Return one active practice plan owned by the authenticated coach."""
    await _ensure_practice_plan_tables(db)
    context = await coach_identity.ensure_recorder_context(db, user)

    row = await _fetch_plan_row(
        db,
        plan_id=plan_id,
        org_id=context.org_id,
        user_id=user.id,
    )
    if row is None:
        raise AppException(
            code="PRACTICE_PLAN_NOT_FOUND",
            message="Practice plan not found",
            status_code=404,
        )

    drills = await _fetch_plan_drills(db, plan_id)
    return _plan_to_response(
        row,
        drills,
        message="Practice plan loaded successfully",
        description=DEFAULT_PLAN_DESCRIPTION,
    )


async def create_coach_practice_plan(
    db: AsyncSession,
    user: User,
    payload: CoachPracticePlanCreateRequest,
) -> dict[str, Any]:
    """Create a practice plan from Edit Practice Plan coach payloads."""
    plan_name = _extract_coach_plan_name(
        plan_name=payload.plan_name,
        title=payload.title,
        name=payload.name,
    )
    drills = await _coach_drills_to_internal(db, payload.drills)
    internal_payload = PracticePlanCreateRequest(
        name=plan_name,
        drills=drills,
        phone=payload.phone,
    )
    result = await create_practice_plan(db, user, internal_payload)
    result["description"] = _coach_plan_description(payload.description)
    return result


async def update_coach_practice_plan(
    db: AsyncSession,
    user: User,
    plan_id: UUID,
    payload: CoachPracticePlanUpdateRequest,
) -> dict[str, Any]:
    """Update a practice plan from Edit Practice Plan coach payloads."""
    name: str | None = None
    if payload.plan_name is not None or payload.title is not None or payload.name is not None:
        name = _extract_coach_plan_name(
            plan_name=payload.plan_name,
            title=payload.title,
            name=payload.name,
        )

    drills: list[PracticePlanDrillInput] | None = None
    if payload.drills is not None:
        drills = await _coach_drills_to_internal(db, payload.drills)

    if name is None and drills is None and payload.description is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one field must be provided to update a practice plan",
            status_code=400,
            details=[
                {
                    "field": "plan_name",
                    "message": "Provide plan_name, title, name, description, and/or drills",
                }
            ],
        )

    if name is None and drills is None:
        result = await get_practice_plan(db, user, plan_id)
        result["description"] = _coach_plan_description(payload.description)
        result["message"] = "Practice plan updated successfully"
        return result

    internal_payload = PracticePlanUpdateRequest(
        name=name,
        drills=drills,
        phone=payload.phone,
    )
    result = await update_practice_plan(db, user, plan_id, internal_payload)
    if payload.description is not None:
        result["description"] = _coach_plan_description(payload.description)
    return result
