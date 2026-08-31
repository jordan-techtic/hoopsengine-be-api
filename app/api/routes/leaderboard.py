"""Leaderboard endpoints for coaches and authenticated players."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach, get_current_user
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.enums import LeaderboardFilterMetric
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.leaderboard import (
    LeaderboardListResponse,
    LeaderboardSearchRequest,
)
from app.services import leaderboard as leaderboard_service
from app.services import player_leaderboard as player_leaderboard_service

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
}

COACH_AUTH_ERROR_RESPONSES = {
    **AUTH_ERROR_RESPONSES,
    403: openapi_error(
        "User is not an authenticated verified coach",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSE = {
    400: openapi_error(
        "Empty or missing search query",
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
        "Request validation failed",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "No players match the search criteria",
        code="PLAYERS_NOT_FOUND",
        message="No players match the search criteria",
    ),
}


def _validate_optional_phone(phone: str | None) -> None:
    """Validate optional Figma status-bar phone metadata when provided."""
    if phone is None or not phone.strip():
        return
    cleaned = phone.strip()
    if len(cleaned) > 30:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number is invalid",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number is invalid"}],
        )
    if not re.sub(r"\D", "", cleaned):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number must contain at least one digit",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number must contain at least one digit"}],
        )


@router.get(
    "",
    response_model=LeaderboardListResponse,
    operation_id="getLeaderboard",
    summary="Get leaderboard rankings",
    description=(
        "Return ranked player statistics including names, shooting percentages, attempts, "
        "and makes for the authenticated user's organization.\n\n"
        "Optional query parameters `search_query` and/or `full_name` filter players by "
        "name. When either is provided, an empty value returns **400** and no matches "
        "return **404**.\n\n"
        "Optional `phone` is client metadata echoed in the response and not persisted.\n\n"
        "An empty `items` array is a valid success response when listing all players "
        "without a search filter.\n\n"
        "**Requires authenticated user JWT (player or coach).**"
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_leaderboard(
    search_query: str | None = Query(
        default=None,
        description="Optional player name search text",
        examples=["Jane"],
    ),
    full_name: str | None = Query(
        default=None,
        description="Figma name container search text",
        examples=["Jane Doe"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    org_id: UUID | None = Query(
        default=None,
        description="Optional organization UUID override to scope leaderboard results",
        examples=["00000000-0000-4000-8000-000000000010"],
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardListResponse:
    _validate_optional_phone(phone)
    result = await player_leaderboard_service.get_authenticated_leaderboard(
        db,
        current_user,
        search_query=search_query,
        full_name=full_name,
        phone=phone,
        org_id=org_id,
    )
    return LeaderboardListResponse(**result)


@router.post(
    "/search",
    response_model=LeaderboardListResponse,
    operation_id="searchLeaderboardPost",
    summary="Search leaderboard players by name (POST)",
    description=(
        "Search for players by name within the authenticated coach's organization.\n\n"
        "Accepts `search_query` and/or Figma `full_name`. Optional `phone` is client "
        "metadata and is not persisted.\n\n"
        "Returns **400** when both search fields are empty.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **COACH_AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def search_leaderboard_post(
    body: LeaderboardSearchRequest,
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardListResponse:
    result = await leaderboard_service.search_players(
        db,
        current_user,
        search_query=body.search_query,
        full_name=body.full_name,
    )
    return LeaderboardListResponse(**result)


@router.get(
    "/search",
    response_model=LeaderboardListResponse,
    operation_id="searchLeaderboardGet",
    summary="Search leaderboard players by name (GET)",
    description=(
        "Search for players by name using query parameters.\n\n"
        "Provide `search_query` and/or `full_name`. Returns **400** when both are empty "
        "and **404** when no players match.\n\n"
        "Optional `phone` is client metadata echoed in the response and not persisted.\n\n"
        "**Requires authenticated user JWT (player or coach).**"
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def search_leaderboard_get(
    search_query: str | None = Query(
        default=None,
        description="Player name search text",
        examples=["Jane"],
    ),
    full_name: str | None = Query(
        default=None,
        description="Figma name container search text",
        examples=["Jane Doe"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardListResponse:
    _validate_optional_phone(phone)
    result = await player_leaderboard_service.search_authenticated_leaderboard(
        db,
        current_user,
        search_query=search_query,
        full_name=full_name,
        phone=phone,
    )
    return LeaderboardListResponse(**result)


@router.get(
    "/filter",
    response_model=LeaderboardListResponse,
    operation_id="filterLeaderboard",
    summary="Filter leaderboard by performance metric",
    description=(
        "Return leaderboard rows sorted by the selected metric:\n\n"
        "- `shooting_percent` (default)\n"
        "- `attempts`\n"
        "- `makes`\n\n"
        "Results are scoped to the authenticated coach's organization.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **COACH_AUTH_ERROR_RESPONSES,
        422: openapi_error(
            "Invalid filter_metric value",
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
async def filter_leaderboard(
    filter_metric: LeaderboardFilterMetric = Query(
        default=LeaderboardFilterMetric.SHOOTING_PERCENT,
        description="Performance metric used to rank players",
        examples=[LeaderboardFilterMetric.SHOOTING_PERCENT],
    ),
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardListResponse:
    result = await leaderboard_service.filter_leaderboard(
        db,
        current_user,
        filter_metric=filter_metric,
    )
    return LeaderboardListResponse(**result)
