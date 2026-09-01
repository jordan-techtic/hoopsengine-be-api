"""Organization admin coach edit endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_admin_coach import (
    OrgAdminCoachDetailResponse,
    OrgAdminCoachRemovalRequest,
    OrgAdminCoachUpdateRequest,
)
from app.services import org_admin_coach as org_admin_coach_service

router = APIRouter(prefix="/admin/coaches", tags=["org-admin-coaches"])

COACH_ID_PATH = Path(
    ...,
    description="Coach UUID",
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

EDIT_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid Edit Coach fields",
        examples={
            "empty_full_name": {
                "code": "VALIDATION_ERROR",
                "message": "Full name is required",
                "details": [{"field": "full_name", "message": "Full name is required"}],
            },
            "empty_email": {
                "code": "VALIDATION_ERROR",
                "message": "Email is required",
                "details": [{"field": "email", "message": "Email is required"}],
            },
            "empty_phone": {
                "code": "VALIDATION_ERROR",
                "message": "Phone is required",
                "details": [{"field": "phone", "message": "Phone is required"}],
            },
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
            },
            "invalid_phone": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid phone number",
                "details": [{"field": "phone", "message": "Enter a valid phone number"}],
            },
            "invalid_team_assignment": {
                "code": "VALIDATION_ERROR",
                "message": "Selected team was not found in your organization",
                "details": [
                    {
                        "field": "team_assignment",
                        "message": "Selected team was not found in your organization",
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

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "Coach not found in the organization",
        code="COACH_NOT_FOUND",
        message="Coach not found",
        details=[{"field": "coach_id", "message": "Coach not found"}],
    ),
}

EDIT_CONFLICT_ERROR_RESPONSE = {
    409: openapi_error(
        "Email already registered to another coach or user account",
        code="EMAIL_ALREADY_IN_USE",
        message="This email is already in use by another account",
        details=[
            {
                "field": "email",
                "message": "This email is already in use by another account",
            }
        ],
    ),
}

REMOVAL_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Invalid Remove Coach parameters",
        examples={
            "invalid_phone": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid phone number",
                "details": [{"field": "phone", "message": "Enter a valid phone number"}],
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
    "/{coach_id}",
    response_model=OrgAdminCoachDetailResponse,
    operation_id="getOrgAdminCoachForEdit",
    summary="Retrieve coach details",
    description=(
        "Return coach profile details for Organization Admin coach management.\n\n"
        "Supports the **Edit Coach** screen (HE-375) and **Remove Coach** screen "
        "(HE-369) from the same endpoint.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`).\n\n"
        "Includes Figma fields `full_name` (as `name` and `full_name`), `email`, `phone`, "
        "`phone_number`, `team_assignment`, and `team` (team display name). "
        "Also includes `confirmation_message` for the Remove Coach confirmation modal.\n\n"
        "Phone is sourced from the linked coach user account when one exists for the "
        "coach email.\n\n"
        "Returns **404** when the coach does not exist or is outside the admin's organization."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        503: openapi_error(
            "Coaches table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Coach operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_org_admin_coach_for_edit(
    coach_id: UUID = COACH_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminCoachDetailResponse:
    """Retrieve coach details for the Edit Coach screen."""
    result = await org_admin_coach_service.get_coach_detail(db, current_user, coach_id)
    return OrgAdminCoachDetailResponse(**result)


@router.put(
    "/{coach_id}",
    response_model=OrgAdminCoachDetailResponse,
    operation_id="updateOrgAdminCoach",
    summary="Update coach details",
    description=(
        "Update a coach record from the Organization Admin **Edit Coach** screen "
        "(HE-375).\n\n"
        "Accepts Figma fields `full_name`, `email`, `phone`, and optional "
        "`team_assignment`. Optional legacy field `name` is also supported as an alias "
        "for `full_name`.\n\n"
        "All contact fields are required. Email must be unique across user accounts "
        "and within the organization's coach roster.\n\n"
        "Returns **200** with updated coach details on success.\n\n"
        "Returns **400** when required fields are empty, email format is invalid, "
        "phone format is invalid, or team assignment is not found.\n\n"
        "Returns **404** when the coach is not in the admin's organization.\n\n"
        "Returns **409** when the email is already registered to another account.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **EDIT_VALIDATION_ERROR_RESPONSES,
        **EDIT_CONFLICT_ERROR_RESPONSE,
        **NOT_FOUND_ERROR_RESPONSE,
        503: openapi_error(
            "Coaches table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Coach operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def update_org_admin_coach(
    body: OrgAdminCoachUpdateRequest,
    coach_id: UUID = COACH_ID_PATH,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminCoachDetailResponse:
    """Update coach details from the Edit Coach form."""
    result = await org_admin_coach_service.update_coach(db, current_user, coach_id, body)
    return OrgAdminCoachDetailResponse(**result)


@router.delete(
    "/{coach_id}",
    status_code=204,
    operation_id="removeOrgAdminCoach",
    summary="Remove a coach from the organization",
    description=(
        "Permanently remove a coach from the Organization Admin **Remove Coach** flow "
        "(HE-369).\n\n"
        "Accepts an optional request body with Figma field `phone` (status bar metadata). "
        "When `phone` is provided it must be a valid phone number; omission is allowed.\n\n"
        "Returns **204 No Content** on successful removal.\n\n"
        "Returns **400** when optional `phone` is present but invalid.\n\n"
        "Returns **404** when the coach is not in the admin's organization.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **REMOVAL_VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        503: openapi_error(
            "Coaches table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Coach operations are temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def remove_org_admin_coach(
    coach_id: UUID = COACH_ID_PATH,
    body: OrgAdminCoachRemovalRequest | None = Body(default=None),
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Remove a coach from the organization."""
    await org_admin_coach_service.remove_coach(db, current_user, coach_id, body)
    return Response(status_code=204)
