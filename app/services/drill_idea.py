"""Business logic for coach drill idea submissions."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.user import User
from app.schemas.drill_idea import DrillIdeaCreateRequest
from app.services import client_db, coach_identity

logger = logging.getLogger(__name__)

DRILL_SUBMISSIONS_TABLE = "drill_submissions"
DRILLS_TABLE = "drills"

ALLOWED_DIFFICULTY_LEVELS = frozenset({"beginner", "intermediate", "advanced"})


def _require_non_empty(value: str | None, field: str, label: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{label} is required",
            status_code=400,
            details=[{"field": field, "message": f"{label} is required"}],
        )
    return cleaned


def _resolve_drill_name(payload: DrillIdeaCreateRequest) -> str:
    """Return drill name from drill_name or Figma full_name alias."""
    if payload.drill_name and payload.drill_name.strip():
        return _require_non_empty(payload.drill_name, "drill_name", "Drill name")
    if payload.full_name and payload.full_name.strip():
        return _require_non_empty(payload.full_name, "full_name", "Drill name")
    raise AppException(
        code="VALIDATION_ERROR",
        message="Drill name is required",
        status_code=400,
        details=[{"field": "drill_name", "message": "Drill name is required"}],
    )


def _validate_difficulty_level(value: str) -> str:
    cleaned = _require_non_empty(value, "difficulty_level", "Difficulty level")
    normalized = cleaned.lower()
    if normalized not in ALLOWED_DIFFICULTY_LEVELS:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Difficulty level must be Beginner, Intermediate, or Advanced",
            status_code=400,
            details=[
                {
                    "field": "difficulty_level",
                    "message": "Difficulty level must be Beginner, Intermediate, or Advanced",
                }
            ],
        )
    return cleaned.title() if normalized != "intermediate" else "Intermediate"


def _item_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": UUID(str(row["id"])),
        "name": str(row["drill_name"]),
        "category": str(row.get("category") or ""),
        "difficulty_level": str(row.get("description") or ""),
        "instructions": str(row.get("directions") or ""),
        "status": str(row.get("status") or "pending"),
    }


async def _submission_name_exists(
    db: AsyncSession,
    *,
    org_id: UUID,
    drill_name: str,
) -> bool:
    if await client_db.table_exists(db, DRILL_SUBMISSIONS_TABLE):
        result = await db.execute(
            text(
                """
                SELECT id
                FROM drill_submissions
                WHERE org_id = :org_id
                  AND LOWER(drill_name) = LOWER(:drill_name)
                LIMIT 1
                """
            ),
            {"org_id": org_id, "drill_name": drill_name},
        )
        if result.scalar_one_or_none() is not None:
            return True

    if await client_db.table_exists(db, DRILLS_TABLE):
        result = await db.execute(
            text(
                """
                SELECT id
                FROM drills
                WHERE LOWER(name) = LOWER(:drill_name)
                LIMIT 1
                """
            ),
            {"drill_name": drill_name},
        )
        if result.scalar_one_or_none() is not None:
            return True

    return False


async def submit_drill_idea(
    db: AsyncSession,
    user: User,
    payload: DrillIdeaCreateRequest,
) -> dict[str, Any]:
    """Create a new drill idea submission for the authenticated coach."""
    await client_db.require_table(db, DRILL_SUBMISSIONS_TABLE)
    recorder = await coach_identity.ensure_recorder_context(db, user)

    drill_name = _resolve_drill_name(payload)
    category = _require_non_empty(payload.category, "category", "Category")
    difficulty_level = _validate_difficulty_level(payload.difficulty_level)
    instructions = _require_non_empty(payload.instructions, "instructions", "Instructions")

    if await _submission_name_exists(db, org_id=recorder.org_id, drill_name=drill_name):
        raise AppException(
            code="DRILL_IDEA_ALREADY_EXISTS",
            message="A drill with this name already exists",
            status_code=409,
            details=[
                {
                    "field": "drill_name",
                    "message": "A drill with this name already exists",
                }
            ],
        )

    submission_id = uuid.uuid4()
    await db.execute(
        text(
            """
            INSERT INTO drill_submissions (
                id,
                org_id,
                submitted_by,
                drill_name,
                category,
                description,
                directions,
                status
            ) VALUES (
                :id,
                :org_id,
                :submitted_by,
                :drill_name,
                :category,
                :description,
                :directions,
                'pending'
            )
            """
        ),
        {
            "id": submission_id,
            "org_id": recorder.org_id,
            "submitted_by": recorder.coach_id,
            "drill_name": drill_name,
            "category": category,
            "description": difficulty_level,
            "directions": instructions,
        },
    )
    await db.commit()

    logger.info("Coach %s submitted drill idea %s", user.id, submission_id)
    return {
        "success": True,
        "message": "Drill idea submitted successfully",
        "status": "submitted",
        "description": "Your drill idea has been sent for review",
        "link": f"{settings.API_V1_PREFIX}/drill-ideas",
        "error": None,
        "id": submission_id,
        "name": drill_name,
        "category": category,
        "difficulty_level": difficulty_level,
        "instructions": instructions,
    }


async def list_drill_ideas(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return drill idea submissions for the authenticated coach's organization."""
    await client_db.require_table(db, DRILL_SUBMISSIONS_TABLE)
    recorder = await coach_identity.ensure_recorder_context(db, user)

    result = await db.execute(
        text(
            """
            SELECT id, drill_name, category, description, directions, status
            FROM drill_submissions
            WHERE org_id = :org_id
            ORDER BY submitted_at DESC NULLS LAST, drill_name ASC
            """
        ),
        {"org_id": recorder.org_id},
    )
    items = [_item_from_row(dict(row)) for row in result.mappings().all()]

    logger.info("Listed %d drill ideas for coach %s", len(items), user.id)
    return {
        "success": True,
        "message": "Drill ideas loaded successfully" if items else "No drill ideas submitted yet",
        "status": "ready",
        "description": "Submitted custom drill ideas",
        "link": None,
        "error": None,
        "id": items[0]["id"] if items else None,
        "drill_ideas": items,
    }
