"""One Drill Step-1 endpoints for player search, selection, and continue."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.coach_drill_flow import (
    CoachDrillContinueRequest,
    CoachDrillContinueResponse,
    CoachDrillSearchRequest,
    CoachDrillSearchResponse,
    CoachDrillSelectPlayerRequest,
    CoachDrillSelectPlayerResponse,
)
from app.schemas.errors import openapi_error
from app.services import one_drill_flow as one_drill_flow_service

router = APIRouter(prefix="/coach/drills", tags=["coach-one-drill"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "User is not an authenticated verified coach",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

SEARCH_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Missing or empty search query",
        code="VALIDATION_ERROR",
        message="Search query is required",
        details=[
            {
                "field": "search_query",
                "message": "Provide search_query or full_name to search players",
            }
        ],
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

SELECT_ERROR_RESPONSES = {
    409: openapi_error(
        "Selected player is not available",
        code="PLAYER_NOT_FOUND",
        message="Selected player is not available in your organization",
        details=[
            {
                "field": "selected_player_id",
                "message": "Selected player is not available in your organization",
            }
        ],
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

CONTINUE_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Player not selected before continue",
        code="VALIDATION_ERROR",
        message="Select a player before continuing",
        details=[
            {
                "field": "selected_player_id",
                "message": "Select a player before continuing to the next step",
            }
        ],
    ),
}


@router.post(
    "/search",
    response_model=CoachDrillSearchResponse,
    operation_id="searchPlayersForOneDrill",
    summary="Search players for One Drill Step-1",
    description=(
        "Search active players in the coach organization by name or jersey number.\n\n"
        "Provide `search_query` and/or the Figma alias `full_name`. At least one must be "
        "non-empty.\n\n"
        "Optional `phone` is client metadata from the status bar and is not persisted.\n\n"
        "Returns **200** with matching players.\n\n"
        "Returns **400** when the search query is empty.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **SEARCH_VALIDATION_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Players table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Player search is temporarily unavailable",
        ),
    },
)
async def search_players_for_one_drill(
    body: CoachDrillSearchRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachDrillSearchResponse:
    result = await one_drill_flow_service.search_players_for_drill(db, current_user, body)
    return CoachDrillSearchResponse(**result)


@router.post(
    "/select_player",
    response_model=CoachDrillSelectPlayerResponse,
    operation_id="selectPlayerForOneDrill",
    summary="Select a player for One Drill Step-1",
    description=(
        "Persist the selected player on the active One Drill session.\n\n"
        "**Required body field:** `selected_player_id`.\n\n"
        "Optional `full_name` and `phone` are client metadata and are not persisted.\n\n"
        "Returns **200** when the player is selected successfully.\n\n"
        "Returns **409** when the player does not exist in the coach organization.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **SELECT_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Session table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Session recording is temporarily unavailable",
        ),
    },
)
async def select_player_for_one_drill(
    body: CoachDrillSelectPlayerRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachDrillSelectPlayerResponse:
    result = await one_drill_flow_service.select_player(db, current_user, body)
    return CoachDrillSelectPlayerResponse(**result)


@router.post(
    "/continue",
    response_model=CoachDrillContinueResponse,
    operation_id="continueOneDrillStep1",
    summary="Continue from One Drill Step-1 to Step-2",
    description=(
        "Advance the One Drill flow to Step 2 after a player has been selected.\n\n"
        "Optional `phone` is client metadata from the status bar and is not persisted.\n\n"
        "Returns **200** when the flow advances successfully.\n\n"
        "Returns **400** when no player was selected.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **CONTINUE_VALIDATION_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Session table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Session recording is temporarily unavailable",
        ),
    },
)
async def continue_one_drill_step1(
    body: CoachDrillContinueRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> CoachDrillContinueResponse:
    result = await one_drill_flow_service.continue_to_next_step(db, current_user, body)
    return CoachDrillContinueResponse(**result)
