"""Drill search endpoints for Create and Edit Practice Plan."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_coach
from app.core.database import get_db
from app.models.user import User
from app.schemas.drill import DrillSearchResponse
from app.schemas.errors import openapi_error
from app.services import drill as drill_service

router = APIRouter(prefix="/drills", tags=["drills"])

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
    400: openapi_error(
        "Missing or empty search query",
        code="VALIDATION_ERROR",
        message="Search query is required",
        details=[{"field": "q", "message": "Search query cannot be empty"}],
    ),
}


@router.get(
    "/search",
    response_model=DrillSearchResponse,
    operation_id="searchDrills",
    summary="Search drills by name",
    description=(
        "Search active drills by name for the Create and Edit Practice Plan drill pickers.\n\n"
        "Provide the `q` query parameter with a non-empty search term. "
        "Only approved/active drills are returned.\n\n"
        "Returns **400** when `q` is missing or blank.\n\n"
        "An empty `drills` array is a valid success response when no drills match.\n\n"
        "**Requires authenticated verified coach JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Drills table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Drill search is temporarily unavailable",
        ),
    },
)
async def search_drills(
    q: str = Query(
        default="",
        description="Case-insensitive drill name search term",
        examples=["warm"],
    ),
    current_user: User = Depends(get_current_coach),
    db: AsyncSession = Depends(get_db),
) -> DrillSearchResponse:
    result = await drill_service.search_drills(db, q)
    return DrillSearchResponse(**result)
