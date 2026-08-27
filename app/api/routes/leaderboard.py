"""Coach leaderboard endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.enums import LeaderboardFilterMetric
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.leaderboard import (
    LeaderboardListResponse,
    LeaderboardSearchRequest,
)
from app.services import leaderboard as leaderboard_service

router = APIRouter(prefix="/leaderboard", tags=["coach-leaderboard"])

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


@router.get(
    "",
    response_model=LeaderboardListResponse,
    operation_id="getLeaderboard",
    summary="Get leaderboard rankings",
    description=(
        "Return ranked player statistics including names, shooting percentages, attempts, "
        "and makes.\n\n"
        "**Public endpoint** — no authentication required.\n\n"
        "Optional `org_id` limits results to one organization; when omitted, rankings "
        "include all organizations.\n\n"
        "An empty `items` array is a valid empty state."
    ),
    responses={
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_leaderboard(
    org_id: UUID | None = Query(
        default=None,
        description="Optional organization UUID to scope leaderboard results",
    ),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardListResponse:
    result = await leaderboard_service.get_leaderboard(db, org_id=org_id)
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
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSE,
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
        "Provide `search_query` and/or `full_name`. Returns **400** when both are empty.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSE,
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
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardListResponse:
    result = await leaderboard_service.search_players(
        db,
        current_user,
        search_query=search_query,
        full_name=full_name,
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
        **AUTH_ERROR_RESPONSES,
        422: openapi_error(
            "Invalid filter_metric value",
            code="VALIDATION_ERROR",
            message="Request validation failed",
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
