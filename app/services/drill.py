"""Business logic for drill catalog APIs (One Drill Step-2 and practice plan search)."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.drill import (
    DrillContinueRequest,
    DrillCreateRequest,
    DrillUpdateRequest,
)
from app.services import client_db, one_drill_flow

logger = logging.getLogger(__name__)

DRILLS_TABLE = "drills"
LIVE_PRACTICE_CATEGORY = "live_practice"
DEFAULT_DRILL_CATEGORY = "general"
LIST_LIMIT = 100


async def _column_exists(db: AsyncSession, column_name: str) -> bool:
    """Return True when a column exists on the drills table."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'drills'
                  AND column_name = :column_name
            )
            """
        ),
        {"column_name": column_name},
    )
    return bool(exists)


async def _approved_column_exists(db: AsyncSession) -> bool:
    """Return True when drills.approved exists."""
    return await _column_exists(db, "approved")


def _resolve_search_term(
    *,
    search: str | None,
    full_name: str | None,
    q: str | None,
) -> str | None:
    """Return the first non-empty search term from supported aliases."""
    for candidate in (search, full_name, q):
        if candidate is not None and candidate.strip():
            return candidate.strip()
    return None


def _validate_search_query(query: str | None) -> str:
    """Return a trimmed search query or raise 400 when empty."""
    cleaned = (query or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Search query is required",
            status_code=400,
            details=[{"field": "q", "message": "Search query cannot be empty"}],
        )
    return cleaned


def _validate_drill_name(name: str | None, *, field: str = "drill_name") -> str:
    """Return a trimmed drill name or raise 400 when empty."""
    cleaned = (name or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Drill name is required",
            status_code=400,
            details=[{"field": field, "message": "Drill name is required"}],
        )
    return cleaned


def _validate_drill_category(category: str | None) -> str:
    """Return a trimmed drill category or raise 400 when empty."""
    cleaned = (category or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Drill category is required",
            status_code=400,
            details=[{"field": "drill_category", "message": "Drill category is required"}],
        )
    return cleaned


def _catalog_filter_sql(*, approved_only: bool) -> str:
    """Build SQL filters excluding live-practice drills from the catalog."""
    approved_sql = "AND d.approved = true" if approved_only else ""
    return f"""
        d.category != :live_practice_category
        {approved_sql}
    """


def _row_image(row: dict[str, Any]) -> str | None:
    """Extract an optional image/thumbnail URL from a drill row."""
    for key in ("animation_svg", "logo_url", "image_url"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _list_item(row: dict[str, Any]) -> dict[str, Any]:
    """Map a drills row to a catalog list item."""
    return {
        "id": UUID(str(row["id"])),
        "name": str(row["name"]),
        "category": str(row.get("category") or DEFAULT_DRILL_CATEGORY),
        "duration": int(row.get("time_seconds") or 0),
        "image": _row_image(row),
    }


def _mutation_payload(row: dict[str, Any], *, message: str) -> dict[str, Any]:
    """Build a create/update response envelope."""
    item = _list_item(row)
    return {
        "success": True,
        "message": message,
        "status": "ready",
        "description": "Drill is available for selection",
        "link": None,
        "error": None,
        **item,
    }


async def _select_drill_columns(db: AsyncSession) -> str:
    """Return SELECT column list for drill rows."""
    parts = ["d.id", "d.name", "d.category"]
    if await _column_exists(db, "time_seconds"):
        parts.append("d.time_seconds")
    else:
        parts.append("NULL AS time_seconds")
    if await _column_exists(db, "description"):
        parts.append("d.description")
    else:
        parts.append("NULL AS description")
    if await _column_exists(db, "animation_svg"):
        parts.append("d.animation_svg")
    else:
        parts.append("NULL AS animation_svg")
    if await _column_exists(db, "submitted_by_org"):
        parts.append("d.submitted_by_org")
    else:
        parts.append("NULL AS submitted_by_org")
    if await _column_exists(db, "approved"):
        parts.append("d.approved")
    else:
        parts.append("NULL AS approved")
    return ", ".join(parts)


async def _fetch_catalog_drills(
    db: AsyncSession,
    *,
    search_term: str | None = None,
    limit: int = LIST_LIMIT,
) -> list[dict[str, Any]]:
    """Load approved catalog drills, optionally filtered by name."""
    await client_db.require_table(db, DRILLS_TABLE)
    approved_exists = await _approved_column_exists(db)
    select_sql = await _select_drill_columns(db)

    search_sql = ""
    params: dict[str, Any] = {
        "live_practice_category": LIVE_PRACTICE_CATEGORY,
        "limit": limit,
    }
    if search_term:
        params["pattern"] = f"%{search_term}%"
        search_sql = "AND d.name ILIKE :pattern"

    result = await db.execute(
        text(
            f"""
            SELECT {select_sql}
            FROM drills d
            WHERE {_catalog_filter_sql(approved_only=approved_exists)}
              {search_sql}
            ORDER BY d.name ASC
            LIMIT :limit
            """
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()]


async def _fetch_drill_row(db: AsyncSession, drill_id: UUID) -> dict[str, Any] | None:
    """Load one drill row by id."""
    select_sql = await _select_drill_columns(db)
    result = await db.execute(
        text(
            f"""
            SELECT {select_sql}
            FROM drills d
            WHERE d.id = :drill_id
            LIMIT 1
            """
        ),
        {"drill_id": drill_id},
    )
    row = result.mappings().first()
    return dict(row) if row is not None else None


async def _assert_catalog_drill(db: AsyncSession, drill_id: UUID) -> dict[str, Any]:
    """Return a catalog drill row or raise 404."""
    row = await _fetch_drill_row(db, drill_id)
    if row is None or str(row.get("category")) == LIVE_PRACTICE_CATEGORY:
        raise AppException(
            code="DRILL_NOT_FOUND",
            message="Drill not found",
            status_code=404,
            details=[{"field": "id", "message": "Drill not found"}],
        )
    if await _approved_column_exists(db):
        approved = row.get("approved")
        if approved is False:
            raise AppException(
                code="DRILL_NOT_FOUND",
                message="Drill not found",
                status_code=404,
                details=[{"field": "id", "message": "Drill not found"}],
            )
    return row


async def _drill_name_exists(
    db: AsyncSession,
    name: str,
    *,
    exclude_id: UUID | None = None,
) -> bool:
    """Return True when another drill already uses this name."""
    params: dict[str, Any] = {"name": name}
    exclude_sql = ""
    if exclude_id is not None:
        exclude_sql = "AND id != :exclude_id"
        params["exclude_id"] = exclude_id
    result = await db.execute(
        text(
            f"""
            SELECT id
            FROM drills
            WHERE LOWER(name) = LOWER(:name)
              {exclude_sql}
            LIMIT 1
            """
        ),
        params,
    )
    return result.scalar_one_or_none() is not None


def _ensure_coach_org(user: User) -> UUID:
    """Return the coach organization id or raise 400."""
    if user.org_id is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Coach must belong to an organization to manage drills",
            status_code=400,
            details=[
                {
                    "field": "org_id",
                    "message": "Coach must belong to an organization to manage drills",
                }
            ],
        )
    return user.org_id


async def search_drills(db: AsyncSession, query: str | None) -> dict[str, Any]:
    """Search active drills by name for the Edit Practice Plan drill picker."""
    cleaned = _validate_search_query(query)
    rows = await _fetch_catalog_drills(db, search_term=cleaned)

    drills = [
        {
            "id": item["id"],
            "name": item["name"],
            "type": item["category"],
        }
        for item in (_list_item(row) for row in rows)
    ]

    logger.info("Drill search for %r returned %d results", cleaned, len(drills))
    return {
        "success": True,
        "message": "Drills found" if drills else "No drills matched your search",
        "status": "ready",
        "description": "Matching active drills",
        "link": None,
        "error": None,
        "drills": drills,
    }


async def list_drills(
    db: AsyncSession,
    *,
    search: str | None = None,
    full_name: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    """List approved catalog drills for One Drill Step-2, optionally filtered by name."""
    term = _resolve_search_term(search=search, full_name=full_name, q=q)
    rows = await _fetch_catalog_drills(db, search_term=term)
    items = [_list_item(row) for row in rows]

    logger.info("Listed %d catalog drills (search=%r)", len(items), term)
    return {
        "success": True,
        "message": "Drills loaded successfully" if items else "No drills available",
        "status": "ready",
        "description": "Choose a drill to track performance metrics",
        "link": None,
        "error": None,
        "search": term,
        "full_name": full_name.strip() if full_name and full_name.strip() else None,
        "drills": items,
    }


async def get_drill(db: AsyncSession, drill_id: UUID) -> dict[str, Any]:
    """Return drill details for One Drill Step-2."""
    row = await _assert_catalog_drill(db, drill_id)
    item = _list_item(row)
    description = row.get("description")
    return {
        "success": True,
        "message": "Drill details loaded successfully",
        "status": "ready",
        "description": str(description) if description else "Focus on a single drill and track performance",
        "link": None,
        "error": None,
        **item,
    }


async def create_drill(
    db: AsyncSession,
    user: User,
    payload: DrillCreateRequest,
) -> dict[str, Any]:
    """Create a new catalog drill."""
    org_id = _ensure_coach_org(user)
    await client_db.require_table(db, DRILLS_TABLE)

    drill_name = _validate_drill_name(payload.drill_name)
    if not payload.drill_name.strip() and payload.full_name and payload.full_name.strip():
        drill_name = _validate_drill_name(payload.full_name, field="full_name")

    category = _validate_drill_category(payload.drill_category)
    duration = payload.duration if payload.duration is not None else 0

    if await _drill_name_exists(db, drill_name):
        raise AppException(
            code="DRILL_ALREADY_EXISTS",
            message="A drill with this name already exists",
            status_code=409,
            details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
        )

    drill_id = uuid.uuid4()
    columns = ["id", "name", "category"]
    params: dict[str, Any] = {
        "id": drill_id,
        "name": drill_name,
        "category": category,
    }
    if await _column_exists(db, "time_seconds"):
        columns.append("time_seconds")
        params["time_seconds"] = duration
    if await _column_exists(db, "submitted_by_org"):
        columns.append("submitted_by_org")
        params["submitted_by_org"] = org_id
    if await _column_exists(db, "approved"):
        columns.append("approved")
        params["approved"] = True

    placeholders = ", ".join(f":{column}" for column in columns)
    column_sql = ", ".join(columns)
    try:
        await db.execute(
            text(f"INSERT INTO drills ({column_sql}) VALUES ({placeholders})"),
            params,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppException(
            code="DRILL_ALREADY_EXISTS",
            message="A drill with this name already exists",
            status_code=409,
            details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
        ) from exc

    row = await _fetch_drill_row(db, drill_id)
    if row is None:
        raise AppException(
            code="DRILL_CREATE_FAILED",
            message="Could not create the drill",
            status_code=500,
        )

    logger.info("Created catalog drill %s for org %s", drill_id, org_id)
    return _mutation_payload(row, message="Drill created successfully")


async def update_drill(
    db: AsyncSession,
    user: User,
    drill_id: UUID,
    payload: DrillUpdateRequest,
) -> dict[str, Any]:
    """Update an existing catalog drill."""
    _ensure_coach_org(user)
    row = await _assert_catalog_drill(db, drill_id)

    submitted_org = row.get("submitted_by_org")
    if submitted_org is not None and user.org_id is not None:
        if UUID(str(submitted_org)) != user.org_id:
            raise AppException(
                code="FORBIDDEN",
                message="You do not have permission to modify this drill",
                status_code=403,
            )

    updates: dict[str, Any] = {}
    if payload.drill_name is not None:
        updates["name"] = _validate_drill_name(payload.drill_name)
    if payload.drill_category is not None:
        updates["category"] = _validate_drill_category(payload.drill_category)
    if payload.duration is not None and await _column_exists(db, "time_seconds"):
        updates["time_seconds"] = payload.duration

    if not updates:
        raise AppException(
            code="VALIDATION_ERROR",
            message="At least one drill field must be provided",
            status_code=400,
            details=[{"field": "body", "message": "At least one drill field must be provided"}],
        )

    if "name" in updates and await _drill_name_exists(
        db,
        str(updates["name"]),
        exclude_id=drill_id,
    ):
        raise AppException(
            code="DRILL_ALREADY_EXISTS",
            message="A drill with this name already exists",
            status_code=409,
            details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
        )

    set_clauses = ", ".join(f"{column} = :{column}" for column in updates)
    try:
        await db.execute(
            text(f"UPDATE drills SET {set_clauses} WHERE id = :drill_id"),
            {"drill_id": drill_id, **updates},
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppException(
            code="DRILL_ALREADY_EXISTS",
            message="A drill with this name already exists",
            status_code=409,
            details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
        ) from exc

    updated = await _fetch_drill_row(db, drill_id)
    if updated is None:
        raise AppException(
            code="DRILL_NOT_FOUND",
            message="Drill not found",
            status_code=404,
        )
    return _mutation_payload(updated, message="Drill updated successfully")


async def delete_drill(db: AsyncSession, user: User, drill_id: UUID) -> dict[str, Any]:
    """Delete a catalog drill owned by the coach organization."""
    _ensure_coach_org(user)
    row = await _assert_catalog_drill(db, drill_id)

    submitted_org = row.get("submitted_by_org")
    if submitted_org is not None and user.org_id is not None:
        if UUID(str(submitted_org)) != user.org_id:
            raise AppException(
                code="FORBIDDEN",
                message="You do not have permission to modify this drill",
                status_code=403,
            )

    await db.execute(text("DELETE FROM drills WHERE id = :drill_id"), {"drill_id": drill_id})
    await db.commit()
    logger.info("Deleted catalog drill %s", drill_id)
    return {
        "success": True,
        "message": "Drill deleted successfully",
        "status": "ready",
        "description": None,
        "link": None,
        "error": None,
        "id": drill_id,
    }


async def continue_with_drill(
    db: AsyncSession,
    user: User,
    payload: DrillContinueRequest,
) -> dict[str, Any]:
    """Validate drill selection and advance the One Drill flow to step 3."""
    if payload.selected_drill_id is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Selected drill is required",
            status_code=400,
            details=[
                {
                    "field": "selected_drill_id",
                    "message": "Select a drill before continuing",
                }
            ],
        )

    await _assert_catalog_drill(db, payload.selected_drill_id)
    return await one_drill_flow.continue_with_selected_drill(
        db,
        user,
        payload.selected_drill_id,
    )
