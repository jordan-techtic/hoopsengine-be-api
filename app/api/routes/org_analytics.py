"""Organization admin analytics endpoints (HE-452)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_analytics import (
    AnalyticsDashboardResponse,
    AnalyticsExportRequest,
    AnalyticsExportResponse,
    AnalyticsFilterRequest,
)
from app.services import org_analytics as org_analytics_service

router = APIRouter(prefix="/analytics", tags=["org-admin-analytics"])

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
        "Invalid or missing analytics filter parameters or export format",
        examples={
            "invalid_date_range": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid date range",
                "details": [
                    {
                        "field": "filters.date_range",
                        "message": "Date range must use the format YYYY-MM-DD to YYYY-MM-DD",
                    }
                ],
            },
            "invalid_format": {
                "code": "VALIDATION_ERROR",
                "message": "Export format must be csv or pdf",
                "details": [{"field": "format", "message": "Supported formats: csv, pdf"}],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

NOT_FOUND_RESPONSES = {
    404: openapi_error_examples(
        "No analytics data or organization profile found",
        examples={
            "analytics_not_found": {
                "code": "ANALYTICS_NOT_FOUND",
                "message": "No analytics data is available for the selected criteria.",
                "details": None,
            },
            "organization_not_found": {
                "code": "ORGANIZATION_NOT_FOUND",
                "message": "Organization profile not found",
                "details": None,
            },
        },
    ),
}


@router.get(
    "",
    response_model=AnalyticsDashboardResponse,
    operation_id="getOrgAnalyticsDashboard",
    summary="Get analytics dashboard",
    description=(
        "Retrieve analytics dashboard metrics for the authenticated organization admin.\n\n"
        "Returns org-scoped counts for coaches, players, sessions, and shooting performance "
        "using a default all-time date range.\n\n"
        "Returns **404** when no analytics data is available. Returns **404** when the "
        "admin account is not linked to an organization.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_analytics_dashboard(
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsDashboardResponse:
    """Return analytics dashboard data for the org admin."""
    return await org_analytics_service.get_analytics_dashboard(db, current_user)


@router.post(
    "/filter",
    response_model=AnalyticsDashboardResponse,
    operation_id="filterOrgAnalytics",
    summary="Apply analytics filters",
    description=(
        "Apply filter parameters to analytics data and return filtered metrics and insights.\n\n"
        "Accepts `filters.date_range` (for example `2023-01-01 to 2023-12-31`) and optional "
        "`filters.user_segments`.\n\n"
        "Returns **200** with filtered metrics. Returns **400** when filter parameters are "
        "missing or invalid.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def filter_analytics(
    body: AnalyticsFilterRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsDashboardResponse:
    """Apply filters to analytics data."""
    return await org_analytics_service.filter_analytics(db, current_user, body.filters)


@router.post(
    "/export",
    response_model=AnalyticsExportResponse,
    operation_id="exportOrgAnalytics",
    summary="Export analytics insights",
    description=(
        "Export analytics insights derived from the supplied filters as **csv** or **pdf**.\n\n"
        "Returns a success message and base64-encoded file contents.\n\n"
        "Returns **400** when filters or format are invalid. Returns **502** when export "
        "processing fails.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        502: openapi_error(
            "Export processing failed",
            code="EXPORT_FAILED",
            message="Unable to load analytics data due to a network or processing error",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def export_analytics(
    body: AnalyticsExportRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsExportResponse:
    """Export analytics insights in the requested format."""
    return await org_analytics_service.export_analytics(
        db,
        current_user,
        body.filters,
        body.format,
    )
