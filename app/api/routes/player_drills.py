"""Authenticated player Active Drill endpoints (HE-455, HE-213)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.player_drills import (
    PlayerActiveDrillResponse,
    PlayerDrillDetailResponse,
    PlayerDrillListResponse,
    PlayerDrillPlayRequest,
    PlayerDrillTimerRequest,
    PlayerDrillTimerResponse,
    PlayerDrillTimerUpdateRequest,
)
from app.services import player_drills as player_drills_service

router = APIRouter(prefix="/player/drills", tags=["player-drills"])

DRILL_ID_PATH = Path(
    ...,
    description="Drill UUID",
    examples=["11111111-2222-3333-4444-555555555555"],
)

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "Authenticated user is not a player or cannot access the drill",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Invalid request or missing active workout",
        examples={
            "no_workout": {
                "code": "VALIDATION_ERROR",
                "message": "Start a workout before resetting the drill timer",
                "details": [
                    {
                        "field": "workout",
                        "message": "Start a workout before resetting the drill timer",
                    }
                ],
            },
            "wrong_active_drill": {
                "code": "VALIDATION_ERROR",
                "message": "This drill is not the active drill session",
                "details": [
                    {
                        "field": "drill_id",
                        "message": "This drill is not the active drill session",
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
    404: openapi_error_examples(
        "Player or drill not found",
        examples={
            "drill_not_found": {
                "code": "DRILL_NOT_FOUND",
                "message": "Drill not found",
                "details": [{"field": "drill_id", "message": "Drill not found"}],
            },
            "player_not_found": {
                "code": "PLAYER_NOT_FOUND",
                "message": "Player not found",
                "details": [
                    {
                        "field": "player",
                        "message": "No roster profile is linked to this account",
                    }
                ],
            },
        },
    ),
}


@router.get(
    "",
    response_model=PlayerDrillListResponse,
    operation_id="listPlayerDrills",
    summary="List active drills for the authenticated player",
    description=(
        "Return active drills assigned to the authenticated player's subteam.\n\n"
        "Each drill includes `drill_id`, `name`, `duration` (seconds), `status` "
        "(`playing`, `paused`, `stopped`, or `reset`), and `time_remaining` (`MM:SS`).\n\n"
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
            message="Drill operations are temporarily unavailable",
        ),
    },
)
async def list_player_drills(
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerDrillListResponse:
    result = await player_drills_service.list_player_drills(db, current_user, phone=phone)
    return PlayerDrillListResponse(**result)


@router.post(
    "/start",
    response_model=PlayerDrillTimerResponse,
    operation_id="startPlayerDrillTimer",
    summary="Start the timer for the current player drill",
    description=(
        "Start the countdown timer for the current or specified drill.\n\n"
        "Optional body fields:\n\n"
        "- `drill_id` — drill to start (defaults to the current workout drill)\n"
        "- `phone` — client metadata (not persisted)\n\n"
        "Returns `status=playing` and `time_remaining` as `MM:SS`.\n\n"
        "**Requires authenticated player JWT**."
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
async def start_player_drill_timer(
    body: PlayerDrillTimerRequest,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerDrillTimerResponse:
    result = await player_drills_service.start_player_drill_timer(db, current_user, body)
    return PlayerDrillTimerResponse(**result)


@router.post(
    "/reset",
    response_model=PlayerDrillTimerResponse,
    operation_id="resetPlayerDrillTimer",
    summary="Reset the timer for the current player drill",
    description=(
        "Reset the active drill timer to its initial duration.\n\n"
        "Optional body fields:\n\n"
        "- `drill_id` — drill to reset (defaults to the current workout drill)\n"
        "- `phone` — client metadata (not persisted)\n\n"
        "Returns `status=reset` and full `time_remaining`.\n\n"
        "**Requires authenticated player JWT**."
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
async def reset_player_drill_timer(
    body: PlayerDrillTimerRequest,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerDrillTimerResponse:
    result = await player_drills_service.reset_player_drill_timer(db, current_user, body)
    return PlayerDrillTimerResponse(**result)


@router.get(
    "/{drill_id}",
    response_model=PlayerDrillDetailResponse,
    operation_id="getPlayerDrillDetail",
    summary="Get details for a specific player drill",
    description=(
        "Return drill metadata and playback state for one assigned drill (Active Drill 2).\n\n"
        "Includes `id`, `drill_id`, `name`, `description`, `category`, `duration`, "
        "`status` (`playing`, `paused`, `stopped`, or `reset`), `timer` (elapsed MM:SS), "
        "`progress` (0-100), `time_remaining`, and optional `phone` metadata.\n\n"
        "Returns **404** when the drill id is invalid.\n\n"
        "Returns **403** when the drill is not assigned to the player.\n\n"
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
    },
)
async def get_player_drill_detail(
    drill_id: UUID = DRILL_ID_PATH,
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerDrillDetailResponse:
    result = await player_drills_service.get_player_drill_detail(
        db,
        current_user,
        drill_id,
        phone=phone,
    )
    return PlayerDrillDetailResponse(**result)


@router.post(
    "/{drill_id}/play",
    response_model=PlayerActiveDrillResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="playPlayerDrill",
    summary="Start drill playback for Active Drill 2",
    description=(
        "Start playback for the specified drill and return the active drill state.\n\n"
        "Request body fields:\n\n"
        "- `phone` — optional client metadata (not persisted)\n\n"
        "Returns **201** with `id`, `name`, `timer` (elapsed MM:SS), `status=playing`, "
        "`progress`, and `description`.\n\n"
        "Returns **404** when the drill id is invalid.\n\n"
        "Returns **403** when the player is not authorized to play the drill.\n\n"
        "**Requires authenticated player JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
        422: openapi_error(
            "Request body failed schema validation",
            code="VALIDATION_ERROR",
            message="Request validation failed",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def play_player_drill(
    body: PlayerDrillPlayRequest,
    drill_id: UUID = DRILL_ID_PATH,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerActiveDrillResponse:
    result = await player_drills_service.play_player_drill(
        db,
        current_user,
        drill_id,
        phone=body.phone,
    )
    return PlayerActiveDrillResponse(**result)


@router.put(
    "/{drill_id}/timer",
    response_model=PlayerActiveDrillResponse,
    operation_id="updatePlayerDrillTimer",
    summary="Update the timer for an active player drill",
    description=(
        "Update elapsed timer and optional playback status for the active drill session.\n\n"
        "Request body fields:\n\n"
        "- `timer` — elapsed time formatted as MM:SS (required)\n"
        "- `status` — optional playback override (`playing`, `paused`, `stopped`)\n"
        "- `phone` — optional client metadata (not persisted)\n\n"
        "Returns **200** with updated `timer`, `status`, and `progress`.\n\n"
        "Returns **400** when playback has not started or the timer exceeds drill duration.\n\n"
        "Returns **404** when the drill id is invalid.\n\n"
        "Returns **403** when the player is not authorized to modify the drill.\n\n"
        "**Requires authenticated player JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSES,
        422: openapi_error(
            "Request body failed schema validation",
            code="VALIDATION_ERROR",
            message="Request validation failed",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def update_player_drill_timer(
    body: PlayerDrillTimerUpdateRequest,
    drill_id: UUID = DRILL_ID_PATH,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerActiveDrillResponse:
    result = await player_drills_service.update_player_drill_timer(
        db,
        current_user,
        drill_id,
        body,
    )
    return PlayerActiveDrillResponse(**result)


@router.post(
    "/{drill_id}/stop",
    response_model=PlayerDrillTimerResponse,
    operation_id="stopPlayerDrillTimer",
    summary="Stop the timer for a specific player drill",
    description=(
        "Stop the countdown timer for the specified drill.\n\n"
        "Optional body field `phone` is client metadata and is not persisted.\n\n"
        "Returns `status=stopped` and updated `time_remaining`.\n\n"
        "Returns **400** when the drill is not the active session drill.\n\n"
        "**Requires authenticated player JWT**."
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
async def stop_player_drill_timer(
    body: PlayerDrillTimerRequest,
    drill_id: UUID = DRILL_ID_PATH,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerDrillTimerResponse:
    result = await player_drills_service.stop_player_drill_timer(
        db,
        current_user,
        drill_id,
        phone=body.phone,
    )
    return PlayerDrillTimerResponse(**result)

# HE-213 ticket-path alias: /api/v1/drills/{id}* (player JWT only).
# Mounted before coach /drills routes; GET /{id} is role-dispatched in drills.py.
alias_router = APIRouter(prefix="/drills", tags=["player-active-drill"])

ALIAS_AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "Authenticated user is not a player or cannot access the drill",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

ALIAS_NOT_FOUND_ERROR_RESPONSES = {
    404: openapi_error_examples(
        "Player or drill not found",
        examples={
            "drill_not_found": {
                "code": "DRILL_NOT_FOUND",
                "message": "Drill not found",
                "details": [{"field": "drill_id", "message": "Drill not found"}],
            },
        },
    ),
}


@alias_router.get(
    "/{drill_id}",
    response_model=PlayerDrillDetailResponse,
    operation_id="getPlayerActiveDrillDetailTicketPath",
    summary="Get active drill details (HE-213 ticket path alias)",
    description=(
        "Ticket-path alias for **GET /api/v1/drills/{id}** (Active Drill 2).

"
        "Returns player drill playback state including `timer`, `status`, and `progress`.

"
        "**Requires authenticated player JWT**."
    ),
    responses={
        **ALIAS_AUTH_ERROR_RESPONSES,
        **ALIAS_NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
    include_in_schema=True,
)
async def get_player_drill_detail_ticket_path(
    drill_id: UUID = DRILL_ID_PATH,
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerDrillDetailResponse:
    result = await player_drills_service.get_player_drill_detail(
        db,
        current_user,
        drill_id,
        phone=phone,
    )
    return PlayerDrillDetailResponse(**result)


@alias_router.post(
    "/{drill_id}/play",
    response_model=PlayerActiveDrillResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="playPlayerDrillTicketPath",
    summary="Start drill playback (HE-213 ticket path alias)",
    description=(
        "Ticket-path alias for **POST /api/v1/drills/{id}/play**.

"
        "Returns **201** when playback starts.

"
        "**Requires authenticated player JWT**."
    ),
    responses={
        **ALIAS_AUTH_ERROR_RESPONSES,
        **ALIAS_NOT_FOUND_ERROR_RESPONSES,
        422: openapi_error(
            "Request body failed schema validation",
            code="VALIDATION_ERROR",
            message="Request validation failed",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def play_player_drill_ticket_path(
    body: PlayerDrillPlayRequest,
    drill_id: UUID = DRILL_ID_PATH,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerActiveDrillResponse:
    result = await player_drills_service.play_player_drill(
        db,
        current_user,
        drill_id,
        phone=body.phone,
    )
    return PlayerActiveDrillResponse(**result)


@alias_router.put(
    "/{drill_id}/timer",
    response_model=PlayerActiveDrillResponse,
    operation_id="updatePlayerDrillTimerTicketPath",
    summary="Update active drill timer (HE-213 ticket path alias)",
    description=(
        "Ticket-path alias for **PUT /api/v1/drills/{id}/timer**.

"
        "Returns **200** with updated timer state.

"
        "**Requires authenticated player JWT**."
    ),
    responses={
        **ALIAS_AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **ALIAS_NOT_FOUND_ERROR_RESPONSES,
        422: openapi_error(
            "Request body failed schema validation",
            code="VALIDATION_ERROR",
            message="Request validation failed",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def update_player_drill_timer_ticket_path(
    body: PlayerDrillTimerUpdateRequest,
    drill_id: UUID = DRILL_ID_PATH,
    current_user: User = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerActiveDrillResponse:
    result = await player_drills_service.update_player_drill_timer(
        db,
        current_user,
        drill_id,
        body,
    )
    return PlayerActiveDrillResponse(**result)
