"""Business logic for authenticated player drill idea submissions."""

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
from app.schemas.player_drill_submission import PlayerDrillSubmissionCreateRequest
from app.services import client_db, player_identity
from app.services.drill_idea import (
    DRILL_SUBMISSIONS_TABLE,
    _item_from_row,
    _require_non_empty,
    _submission_name_exists,
    _validate_difficulty_level,
)

logger = logging.getLogger(__name__)

PLAYER_SUBMITTER_COLUMN = "submitted_by_player_id"


async def _column_exists(db: AsyncSession, table_name: str, column_name: str) -> bool:
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


def _resolve_drill_name(payload: PlayerDrillSubmissionCreateRequest) -> str:
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


def _item_from_row_for_player(row: dict[str, Any]) -> dict[str, Any]:
    base = _item_from_row(row)
    return {
        **base,
        "description": base["instructions"],
    }


def _player_submitter_filter(has_player_column: bool) -> tuple[str, str]:
    if has_player_column:
        return "submitted_by_player_id = :player_id", PLAYER_SUBMITTER_COLUMN
    return "submitted_by = :player_id", "submitted_by"


async def submit_player_drill_submission(
    db: AsyncSession,
    user: User,
    payload: PlayerDrillSubmissionCreateRequest,
) -> dict[str, Any]:
    """Create a drill submission for the authenticated player."""
    await client_db.require_table(db, DRILL_SUBMISSIONS_TABLE)
    context = await player_identity.ensure_player_context(db, user)
    org_id = context.org_id or user.org_id
    if org_id is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Organization is required to submit a drill idea",
            status_code=400,
            details=[
                {
                    "field": "category",
                    "message": "No organization is linked to this player account",
                }
            ],
        )

    drill_name = _resolve_drill_name(payload)
    category = _require_non_empty(payload.category, "category", "Category")
    difficulty_level = _validate_difficulty_level(payload.difficulty_level)
    description = _require_non_empty(payload.description, "description", "Description")

    if await _submission_name_exists(db, org_id=org_id, drill_name=drill_name):
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
    has_player_column = await _column_exists(db, DRILL_SUBMISSIONS_TABLE, PLAYER_SUBMITTER_COLUMN)

    if has_player_column:
        await db.execute(
            text(
                """
                INSERT INTO drill_submissions (
                    id,
                    org_id,
                    submitted_by,
                    submitted_by_player_id,
                    drill_name,
                    category,
                    description,
                    directions,
                    status
                ) VALUES (
                    :id,
                    :org_id,
                    NULL,
                    :submitted_by_player_id,
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
                "org_id": org_id,
                "submitted_by_player_id": context.player_id,
                "drill_name": drill_name,
                "category": category,
                "description": difficulty_level,
                "directions": description,
            },
        )
    else:
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
                "org_id": org_id,
                "submitted_by": context.player_id,
                "drill_name": drill_name,
                "category": category,
                "description": difficulty_level,
                "directions": description,
            },
        )

    await db.commit()
    logger.info("Player %s submitted drill idea %s", context.player_id, submission_id)
    return {
        "success": True,
        "message": "Drill idea submitted successfully",
        "status": "submitted",
        "description": "Your drill idea has been sent for review",
        "link": f"{settings.API_V1_PREFIX}/player/drill-submissions",
        "error": None,
        "id": submission_id,
        "name": drill_name,
        "category": category,
        "difficulty_level": difficulty_level,
    }


async def list_player_drill_submissions(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return drill submissions created by the authenticated player."""
    await client_db.require_table(db, DRILL_SUBMISSIONS_TABLE)
    context = await player_identity.ensure_player_context(db, user)
    has_player_column = await _column_exists(db, DRILL_SUBMISSIONS_TABLE, PLAYER_SUBMITTER_COLUMN)
    filter_clause, _ = _player_submitter_filter(has_player_column)

    result = await db.execute(
        text(
            f"""
            SELECT id, drill_name, category, description, directions, status
            FROM drill_submissions
            WHERE {filter_clause}
            ORDER BY submitted_at DESC NULLS LAST, drill_name ASC
            """
        ),
        {"player_id": context.player_id},
    )
    items = [_item_from_row_for_player(dict(row)) for row in result.mappings().all()]

    logger.info("Listed %d drill submissions for player %s", len(items), context.player_id)
    return {
        "success": True,
        "message": "Drill submissions loaded successfully" if items else "No drill submissions yet",
        "status": "empty" if not items else "ready",
        "description": "Submitted custom drill ideas",
        "link": None,
        "error": None,
        "id": items[0]["id"] if items else None,
        "drill_submissions": items,
    }


async def get_player_drill_submission(
    db: AsyncSession,
    user: User,
    submission_id: UUID,
) -> dict[str, Any]:
    """Return one drill submission owned by the authenticated player."""
    await client_db.require_table(db, DRILL_SUBMISSIONS_TABLE)
    context = await player_identity.ensure_player_context(db, user)
    has_player_column = await _column_exists(db, DRILL_SUBMISSIONS_TABLE, PLAYER_SUBMITTER_COLUMN)
    filter_clause, _ = _player_submitter_filter(has_player_column)

    result = await db.execute(
        text(
            f"""
            SELECT id, drill_name, category, description, directions, status
            FROM drill_submissions
            WHERE id = :submission_id
              AND {filter_clause}
            LIMIT 1
            """
        ),
        {"submission_id": submission_id, "player_id": context.player_id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppException(
            code="DRILL_SUBMISSION_NOT_FOUND",
            message="Drill submission not found",
            status_code=404,
            details=[
                {
                    "field": "id",
                    "message": "Drill submission not found",
                }
            ],
        )

    item = _item_from_row_for_player(dict(row))
    logger.info("Loaded drill submission %s for player %s", submission_id, context.player_id)
    return {
        "success": True,
        "message": "Drill submission loaded successfully",
        "status": "ready",
        "description": item["description"],
        "link": None,
        "error": None,
        "id": item["id"],
        "name": item["name"],
        "category": item["category"],
        "difficulty_level": item["difficulty_level"],
    }
