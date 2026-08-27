"""Public player statistics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.errors import openapi_error
from app.schemas.player_statistics import PlayerStatisticsResponse
from app.services import player_statistics as player_statistics_service

router = APIRouter(prefix="/statistics", tags=["statistics"])

PLAYER_ID_PATH = Path(
    ...,
    description="Player UUID",
    examples=["11111111-2222-3333-4444-555555555555"],
)

NOT_FOUND_ERROR_RESPONSES = {
    404: openapi_error(
        "Player not found",
        code="PLAYER_NOT_FOUND",
        message="Player not found",
    ),
}


@router.get(
    "/{player_id}",
    response_model=PlayerStatisticsResponse,
    operation_id="getPlayerStatistics",
    summary="Get player statistics",
    description=(
        "Retrieve cumulative field-goal statistics and session history for a player.\n\n"
        "Includes mobile envelope fields (`id`, `name`, `status`) plus `active_field_goals`, "
        "`shooting_percentage`, and `session_history`.\n\n"
        "Optional query parameters `full_name` and `phone` are client metadata.\n\n"
        "Returns **400** when `player_id` is missing or not a valid UUID.\n\n"
        "**Public endpoint** — no authentication required."
    ),
    responses={
        **NOT_FOUND_ERROR_RESPONSES,
        400: openapi_error(
            "Invalid player identifier",
            code="VALIDATION_ERROR",
            message="Invalid player_id",
        ),
        422: openapi_error(
            "Request failed schema validation",
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
async def get_player_statistics(
    player_id: str = PLAYER_ID_PATH,
    full_name: str | None = Query(
        default=None,
        description="Optional client metadata from name-meta field",
        examples=["Jane Doe"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar",
        examples=["+1-555-0100"],
    ),
    db: AsyncSession = Depends(get_db),
) -> PlayerStatisticsResponse:
    parsed_player_id = player_statistics_service.parse_player_id(player_id)
    result = await player_statistics_service.get_player_statistics(
        db,
        parsed_player_id,
        full_name=full_name,
        phone=phone,
    )
    return PlayerStatisticsResponse(**result)
