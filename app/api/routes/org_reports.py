"""Organization admin reports endpoints (HE-449)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_reports import (
    ReportDetailResponse,
    ReportExportRequest,
    ReportExportResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
)
from app.services import org_reports as org_reports_service

router = APIRouter(prefix="/reports", tags=["org-admin-reports"])

REPORT_ID_PATH = Path(
    ...,
    description="Generated report UUID",
    examples=["11111111-2222-3333-4444-555555555555"],
)

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
        "Invalid or missing report criteria or export format",
        examples={
            "invalid_date_range": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid date range",
                "details": [
                    {
                        "field": "criteria.date_range",
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
        "Organization profile or report not found",
        examples={
            "report_not_found": {
                "code": "REPORT_NOT_FOUND",
                "message": "Report not found",
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


@router.post(
    "/generate",
    response_model=ReportGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="generateOrgReport",
    summary="Generate organization report",
    description=(
        "Generate a performance report for the authenticated organization admin using "
        "the supplied criteria.\n\n"
        "Accepts `criteria.date_range` (for example `2023-01-01 to 2023-12-31`) and "
        "optional `criteria.user_segments`.\n\n"
        "Returns **201** with report metrics and `report_id` on success. Returns **400** "
        "when the date range is missing or invalid. Returns **404** when the admin account "
        "is not linked to an organization.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`)."
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
async def generate_report(
    body: ReportGenerateRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> ReportGenerateResponse:
    """Generate a report from validated criteria."""
    return await org_reports_service.generate_report(db, current_user, body.criteria)


@router.get(
    "/{report_id}",
    response_model=ReportDetailResponse,
    operation_id="getOrgReport",
    summary="Get generated report details",
    description=(
        "Retrieve a previously generated report by id for the authenticated organization admin.\n\n"
        "Returns **404** when the report does not exist or belongs to another organization.\n\n"
        "**Requires organization admin JWT**."
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
async def get_report(
    report_id: UUID = REPORT_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> ReportDetailResponse:
    """Return report details for the caller's organization."""
    return await org_reports_service.get_report(db, current_user, report_id)


@router.post(
    "/export",
    response_model=ReportExportResponse,
    operation_id="exportOrgReport",
    summary="Export generated report",
    description=(
        "Export a stored report as **csv** or **pdf**. Returns a success message and "
        "base64-encoded file contents.\n\n"
        "Returns **400** when the format is unsupported. Returns **404** when the report "
        "does not exist. Returns **502** when export processing fails.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        502: openapi_error(
            "Export processing failed",
            code="EXPORT_FAILED",
            message="Unable to export the report due to a network or processing error",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def export_report(
    body: ReportExportRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> ReportExportResponse:
    """Export a report in the requested format."""
    return await org_reports_service.export_report(
        db,
        current_user,
        body.report_id,
        body.format,
    )
