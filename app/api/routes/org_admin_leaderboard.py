"""Organization admin leaderboard endpoints (HE-404)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_admin_leaderboard import (
    OrgAdminLeaderboardFilterRequest,
    OrgAdminLeaderboardListResponse,
)
from app.services import org_admin_leaderboard as org_admin_leaderboard_service

router = APIRouter(prefix="/admin/leaderboard", tags=["org-admin-leaderboard"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "Authenticated user is not an organization admin",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Empty search query or invalid optional phone metadata",
        examples={
            "empty_search": {
                "code": "VALIDATION_ERROR",
                "message": "Search query is required",
                "details": [
                    {
                        "field": "search_query",
                        "message": "Provide search_query or full_name to search players",
                    }
                ],
            },
            "invalid_phone": {
                "code": "VALIDATION_ERROR",
                "message": "Phone number must contain at least one digit",
                "details": [
                    {
                        "field": "phone",
                        "message": "Phone number must contain at least one digit",
                    }
                ],
            },
            "invalid_date_range": {
                "code": "VALIDATION_ERROR",
                "message": "Date range start must be on or before end",
                "details": [
                    {
                        "field": "filters.date_range",
                        "message": "start must be on or before end",
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


@router.get(
    "",
    response_model=OrgAdminLeaderboardListResponse,
    operation_id="getOrgAdminLeaderboard",
    summary="Get organization admin leaderboard",
    description=(
        "Return ranked player statistics for the authenticated organization admin's "
        "organization, including player names, shooting percentages, attempts, and makes.\n\n"
        "Optional `phone` is client metadata echoed in the response and not persisted.\n\n"
        "An empty `items` array is a valid success response when no players have recorded "
        "statistics.\n\n"
        "**Requires authenticated organization admin JWT.**"
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
async def get_org_admin_leaderboard(
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminLeaderboardListResponse:
    result = await org_admin_leaderboard_service.get_org_admin_leaderboard(
        db,
        current_user,
        phone=phone,
    )
    return OrgAdminLeaderboardListResponse(**result)


@router.get(
    "/search",
    response_model=OrgAdminLeaderboardListResponse,
    operation_id="searchOrgAdminLeaderboard",
    summary="Search organization admin leaderboard players",
    description=(
        "Search for players by name within the authenticated organization admin's "
        "organization using query parameters.\n\n"
        "Provide `search_query` and/or Figma `full_name`. Returns **400** when both "
        "are empty. Optional `phone` is client metadata and is not persisted.\n\n"
        "Returns **200** with an empty `items` array when no players match.\n\n"
        "**Requires authenticated organization admin JWT.**"
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
async def search_org_admin_leaderboard(
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
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminLeaderboardListResponse:
    result = await org_admin_leaderboard_service.search_org_admin_leaderboard(
        db,
        current_user,
        search_query=search_query,
        full_name=full_name,
        phone=phone,
    )
    return OrgAdminLeaderboardListResponse(**result)


@router.post(
    "/filters",
    response_model=OrgAdminLeaderboardListResponse,
    operation_id="filterOrgAdminLeaderboard",
    summary="Filter organization admin leaderboard rankings",
    description=(
        "Apply ranking filter pills and an optional date range to leaderboard results.\n\n"
        "Supported `filters.ranking` values:\n\n"
        "- `top` — highest performers first\n"
        "- `bottom` — lowest performers first\n\n"
        "Optional `filters.date_range` limits statistics to sessions between the "
        "inclusive start and end dates (YYYY-MM-DD).\n\n"
        "Optional `full_name` and `phone` are client metadata and are not persisted.\n\n"
        "**Requires authenticated organization admin JWT.**"
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
async def filter_org_admin_leaderboard(
    body: OrgAdminLeaderboardFilterRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminLeaderboardListResponse:
    result = await org_admin_leaderboard_service.filter_org_admin_leaderboard(
        db,
        current_user,
        filters=body.filters,
        full_name=body.full_name,
        phone=body.phone,
    )
    return OrgAdminLeaderboardListResponse(**result)
