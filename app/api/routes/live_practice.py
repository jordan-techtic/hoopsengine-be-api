"""Live Practice screen endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.live_practice import (
    LivePracticeDeleteResponse,
    LivePracticeDrillCreateRequest,
    LivePracticeDrillListResponse,
    LivePracticeDrillResponse,
    LivePracticeDrillUpdateRequest,
    LivePracticePlayerStatisticsResponse,
    LivePracticeRecordShotsRequest,
    LivePracticeRecordShotsResponse,
    LivePracticeTimerRequest,
    LivePracticeTimerStatusResponse,
)
from app.services import live_practice as live_practice_service

router = APIRouter(prefix="/live_practice", tags=["live-practice"])

DRILL_ID_PATH = Path(..., description="Live practice drill UUID", examples=["11111111-2222-3333-4444-555555555555"])
PLAYER_ID_PATH = Path(..., description="Player UUID", examples=["11111111-2222-3333-4444-555555555555"])

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

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid live practice fields",
        examples={
            "empty_drill_name": {
                "code": "VALIDATION_ERROR",
                "message": "Drill name is required",
                "details": [{"field": "drill_name", "message": "Drill name is required"}],
            },
            "invalid_duration": {
                "code": "VALIDATION_ERROR",
                "message": "Duration must be at least 1 second",
                "details": [{"field": "duration", "message": "Duration must be at least 1 second"}],
            },
            "invalid_player_stats": {
                "code": "VALIDATION_ERROR",
                "message": "One or more player statistics are invalid",
                "details": [
                    {
                        "field": "player_stats[0].shots_made",
                        "message": "Shots made cannot exceed shots attempted",
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

CONFLICT_ERROR_RESPONSE = {
    409: openapi_error(
        "Drill name already exists",
        code="DRILL_ALREADY_EXISTS",
        message="A drill with this name already exists",
        details=[{"field": "drill_name", "message": "A drill with this name already exists"}],
    ),
}

NOT_FOUND_ERROR_RESPONSES = {
    404: openapi_error_examples(
        "Resource not found",
        examples={
            "drill_not_found": {
                "code": "DRILL_NOT_FOUND",
                "message": "Drill not found",
                "details": [{"field": "id", "message": "Drill not found"}],
            },
            "player_not_found": {
                "code": "PLAYER_NOT_FOUND",
                "message": "Player not found",
                "details": [{"field": "player_id", "message": "Player not found"}],
            },
        },
    ),
}


@router.post(
    "/drills",
    response_model=LivePracticeDrillResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createLivePracticeDrill",
    summary="Create live practice drill",
    description=(
        "Save a new drill for the **Live Practice** screen.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "Accepts `drill_name`, `duration` (seconds), optional `player_stats`, and optional "
        "client metadata `phone` (not persisted).\n\n"
        "Returns **201** when the drill is saved.\n\n"
        "Returns **400** for missing/invalid fields or invalid player statistics.\n\n"
        "Returns **409** when a drill with the same name already exists."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSE,
        503: openapi_error(
            "Drills table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Live practice operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def create_live_practice_drill(
    body: LivePracticeDrillCreateRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> LivePracticeDrillResponse:
    result = await live_practice_service.create_live_practice_drill(db, current_user, body)
    return LivePracticeDrillResponse(**result)


@router.get(
    "/drills",
    response_model=LivePracticeDrillListResponse,
    operation_id="listLivePracticeDrills",
    summary="List live practice drills",
    description=(
        "Return all saved live practice drills.\n\n"
        "**Public endpoint** — no authentication required."
    ),
    responses={
        503: openapi_error(
            "Drills table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Live practice operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def list_live_practice_drills(
    db: AsyncSession = Depends(get_db),
) -> LivePracticeDrillListResponse:
    result = await live_practice_service.list_live_practice_drills(db)
    return LivePracticeDrillListResponse(**result)


@router.put(
    "/drills/{drill_id}",
    response_model=LivePracticeDrillResponse,
    operation_id="updateLivePracticeDrill",
    summary="Update live practice drill",
    description=(
        "Update an existing live practice drill.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "Returns **404** when the drill is not found.\n\n"
        "Returns **409** when renaming to an existing drill name."
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
    },
)
async def update_live_practice_drill(
    body: LivePracticeDrillUpdateRequest,
    drill_id: UUID = DRILL_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> LivePracticeDrillResponse:
    result = await live_practice_service.update_live_practice_drill(
        db, current_user, drill_id, body
    )
    return LivePracticeDrillResponse(**result)


@router.delete(
    "/drills/{drill_id}",
    response_model=LivePracticeDeleteResponse,
    operation_id="deleteLivePracticeDrill",
    summary="Delete live practice drill",
    description=(
        "Delete a live practice drill.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "Returns **404** when the drill is not found."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def delete_live_practice_drill(
    drill_id: UUID = DRILL_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> LivePracticeDeleteResponse:
    result = await live_practice_service.delete_live_practice_drill(db, current_user, drill_id)
    return LivePracticeDeleteResponse(**result)


@router.post(
    "/timer/start",
    response_model=LivePracticeTimerStatusResponse,
    operation_id="startLivePracticeTimer",
    summary="Start live practice timer",
    description=(
        "Start the drill timer for the coach's active live practice session.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "Optional `duration` overrides the configured drill duration. "
        "Optional `phone` is client metadata and is not persisted."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def start_live_practice_timer(
    body: LivePracticeTimerRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> LivePracticeTimerStatusResponse:
    result = await live_practice_service.start_live_practice_timer(db, current_user, body)
    return LivePracticeTimerStatusResponse(**result)


@router.post(
    "/timer/stop",
    response_model=LivePracticeTimerStatusResponse,
    operation_id="stopLivePracticeTimer",
    summary="Stop live practice timer",
    description=(
        "Stop the drill timer and accumulate elapsed seconds.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def stop_live_practice_timer(
    body: LivePracticeTimerRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> LivePracticeTimerStatusResponse:
    result = await live_practice_service.stop_live_practice_timer(db, current_user, body)
    return LivePracticeTimerStatusResponse(**result)


@router.get(
    "/timer/status",
    response_model=LivePracticeTimerStatusResponse,
    operation_id="getLivePracticeTimerStatus",
    summary="Get live practice timer status",
    description=(
        "Return the current timer state for the coach's live practice session.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_live_practice_timer_status(
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> LivePracticeTimerStatusResponse:
    result = await live_practice_service.get_live_practice_timer_status(db, current_user)
    return LivePracticeTimerStatusResponse(**result)


@router.post(
    "/players/{player_id}/shots",
    response_model=LivePracticeRecordShotsResponse,
    operation_id="recordLivePracticeShots",
    summary="Record player shots",
    description=(
        "Record makes and attempts for a player during live practice.\n\n"
        "**Requires authenticated verified coach JWT**.\n\n"
        "Returns **400** when shot counts are invalid.\n\n"
        "Returns **404** when the player or drill is not found."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def record_live_practice_shots(
    body: LivePracticeRecordShotsRequest,
    player_id: UUID = PLAYER_ID_PATH,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> LivePracticeRecordShotsResponse:
    result = await live_practice_service.record_player_shots(db, current_user, player_id, body)
    return LivePracticeRecordShotsResponse(**result)


@router.get(
    "/players/{player_id}/statistics",
    response_model=LivePracticePlayerStatisticsResponse,
    operation_id="getLivePracticePlayerStatistics",
    summary="Get player live practice statistics",
    description=(
        "Retrieve aggregated shot statistics for a player in the active live practice session.\n\n"
        "**Public endpoint** — no authentication required."
    ),
    responses={
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_live_practice_player_statistics(
    player_id: UUID = PLAYER_ID_PATH,
    db: AsyncSession = Depends(get_db),
) -> LivePracticePlayerStatisticsResponse:
    result = await live_practice_service.get_player_statistics(db, player_id)
    return LivePracticePlayerStatisticsResponse(**result)
