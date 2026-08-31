"""Authenticated player drill submission endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.player_drill_submission import (
    PlayerDrillSubmissionCreateRequest,
    PlayerDrillSubmissionCreateResponse,
    PlayerDrillSubmissionDetailResponse,
    PlayerDrillSubmissionListResponse,
)
from app.services import player_drill_submission as player_drill_submission_service

router = APIRouter(prefix="/player/drill-submissions", tags=["player-drill-submissions"])

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

NOT_FOUND_ERROR_RESPONSES = {
    404: openapi_error(
        "Linked player profile or drill submission not found",
        code="DRILL_SUBMISSION_NOT_FOUND",
        message="Drill submission not found",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid drill submission fields",
        examples={
            "missing_drill_name": {
                "code": "VALIDATION_ERROR",
                "message": "Drill name is required",
                "details": [{"field": "drill_name", "message": "Drill name is required"}],
            },
            "empty_category": {
                "code": "VALIDATION_ERROR",
                "message": "Category is required",
                "details": [{"field": "category", "message": "Category is required"}],
            },
            "invalid_difficulty": {
                "code": "VALIDATION_ERROR",
                "message": "Difficulty level must be Beginner, Intermediate, or Advanced",
                "details": [
                    {
                        "field": "difficulty_level",
                        "message": "Difficulty level must be Beginner, Intermediate, or Advanced",
                    }
                ],
            },
            "empty_description": {
                "code": "VALIDATION_ERROR",
                "message": "Description is required",
                "details": [{"field": "description", "message": "Description is required"}],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONFLICT_ERROR_RESPONSE = {
    409: openapi_error(
        "Drill name already exists",
        code="DRILL_IDEA_ALREADY_EXISTS",
        message="A drill with this name already exists",
        details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
    ),
}

SUBMISSION_ID_PATH = Path(
    ...,
    description="Drill submission UUID",
    examples=["11111111-2222-3333-4444-555555555555"],
)


@router.post(
    "",
    response_model=PlayerDrillSubmissionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="submitPlayerDrillSubmission",
    summary="Submit a player drill idea",
    description=(
        "Submit a custom drill idea from the player **Drill-idea submission** screen.\n\n"
        "**Required body fields:** `drill_name` (or Figma alias `full_name`), `category`, "
        "`difficulty_level`, and `description`.\n\n"
        "`difficulty_level` must be one of: **Beginner**, **Intermediate**, or **Advanced**.\n\n"
        "Optional `phone` is client metadata from the status bar and is not persisted.\n\n"
        "Returns **201** when the drill idea is submitted successfully.\n\n"
        "Returns **400** when required fields are missing or invalid.\n\n"
        "Returns **409** when a drill with the same name already exists.\n\n"
        "**Requires authenticated player JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Drill submissions table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Drill submission is temporarily unavailable",
        ),
    },
)
async def submit_player_drill_submission(
    body: PlayerDrillSubmissionCreateRequest,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerDrillSubmissionCreateResponse:
    """Submit a drill idea for the authenticated player."""
    result = await player_drill_submission_service.submit_player_drill_submission(
        db,
        current_user,
        body,
    )
    return PlayerDrillSubmissionCreateResponse(**result)


@router.get(
    "",
    response_model=PlayerDrillSubmissionListResponse,
    operation_id="listPlayerDrillSubmissions",
    summary="List player drill submissions",
    description=(
        "Return drill ideas submitted by the authenticated player.\n\n"
        "Each item includes `id`, `name`, `category`, `difficulty_level`, `description`, "
        "and review `status`.\n\n"
        "Returns **200** with an empty `drill_submissions` array and `status=empty` when "
        "none exist.\n\n"
        "**Requires authenticated player JWT**."
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
            "Drill submissions table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Drill submission is temporarily unavailable",
        ),
    },
)
async def list_player_drill_submissions(
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerDrillSubmissionListResponse:
    """List drill submissions for the authenticated player."""
    result = await player_drill_submission_service.list_player_drill_submissions(
        db,
        current_user,
    )
    return PlayerDrillSubmissionListResponse(**result)


@router.get(
    "/{submission_id}",
    response_model=PlayerDrillSubmissionDetailResponse,
    operation_id="getPlayerDrillSubmission",
    summary="Get player drill submission by ID",
    description=(
        "Return details for a single drill submission owned by the authenticated player.\n\n"
        "Returns **404** when the submission does not exist or belongs to another player.\n\n"
        "**Requires authenticated player JWT**."
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
            "Drill submissions table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Drill submission is temporarily unavailable",
        ),
    },
)
async def get_player_drill_submission(
    submission_id: UUID = SUBMISSION_ID_PATH,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerDrillSubmissionDetailResponse:
    """Return one drill submission for the authenticated player."""
    result = await player_drill_submission_service.get_player_drill_submission(
        db,
        current_user,
        submission_id,
    )
    return PlayerDrillSubmissionDetailResponse(**result)
