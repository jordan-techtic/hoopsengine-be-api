"""Authenticated player Start screen endpoints (HE-229)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.player_start import (
    PlayerStartGetResponse,
    PlayerStartPostResponse,
    PlayerStartWorkoutRequest,
)
from app.services import player_start as player_start_service

router = APIRouter(prefix="/player/start", tags=["player-start"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "Authenticated user is not a player",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Invalid workout request",
        examples={
            "missing_drills": {
                "code": "VALIDATION_ERROR",
                "message": "At least one drill is required to start a workout",
                "details": [
                    {
                        "field": "drills",
                        "message": "At least one drill is required to start a workout",
                    }
                ],
            },
            "blank_drill_name": {
                "code": "VALIDATION_ERROR",
                "message": "Drill name is required",
                "details": [{"field": "drills[0].name", "message": "Drill name is required"}],
            },
            "invalid_duration": {
                "code": "VALIDATION_ERROR",
                "message": "Drill duration must be at least 1 minute",
                "details": [
                    {
                        "field": "drills[0].duration",
                        "message": "Drill duration must be at least 1 minute",
                    }
                ],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

NOT_FOUND_ERROR_RESPONSES = {
    404: openapi_error(
        "No roster profile is linked to the authenticated account",
        code="PLAYER_NOT_FOUND",
        message="Player not found",
        details=[
            {
                "field": "player",
                "message": "No roster profile is linked to this account",
            }
        ],
    ),
}

CONFLICT_ERROR_RESPONSES = {
    409: openapi_error(
        "An in-progress workout already exists for today",
        code="WORKOUT_ALREADY_ACTIVE",
        message="A workout is already in progress for today",
        details=[
            {
                "field": "workout",
                "message": "A workout is already in progress for today",
            }
        ],
    ),
}


@router.get(
    "",
    response_model=PlayerStartGetResponse,
    operation_id="getPlayerStart",
    summary="Get workout statistics and today's drill list",
    description=(
        "Return quick stats and today's assigned drills for the **Start** screen.\n\n"
        "Includes `statistics` (`total_sessions`, `total_attempts`, `shooting_percentage`, "
        "`drill_count`, `total_duration_minutes`), `drills`, and `workout_id` when an "
        "in-progress session exists for today.\n\n"
        "Optional query parameter `phone` is Figma client metadata and is not persisted.\n\n"
        "**Requires authenticated player JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Client tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Workout operations are temporarily unavailable",
        ),
    },
)
async def get_player_start(
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerStartGetResponse:
    result = await player_start_service.get_player_start(db, current_user, phone=phone)
    return PlayerStartGetResponse(**result)


@router.post(
    "",
    response_model=PlayerStartPostResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="startPlayerWorkout",
    summary="Start a player workout session",
    description=(
        "Create an in-progress player workout session using the submitted drill list.\n\n"
        "Request body fields:\n\n"
        "- `drills` — non-empty list of `{name, duration}` items (duration in minutes)\n"
        "- `workout_id` — optional reserved field (not required to start)\n"
        "- `phone` — optional client metadata (not persisted)\n\n"
        "Returns **201** with `workout_id`, `status=started`, and the submitted drills.\n\n"
        "Returns **409** when a workout is already in progress for today.\n\n"
        "Returns **400** when drills are missing or invalid.\n\n"
        "**Requires authenticated player JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Client tables unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Workout operations are temporarily unavailable",
        ),
    },
)
async def start_player_workout(
    body: PlayerStartWorkoutRequest,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerStartPostResponse:
    result = await player_start_service.start_player_workout(db, current_user, body)
    return PlayerStartPostResponse(**result)
