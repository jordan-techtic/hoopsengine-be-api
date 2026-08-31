"""Organization admin coach invite and search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_admin_invite_coach import (
    OrgAdminInviteCoachRequest,
    OrgAdminInviteCoachResponse,
    OrgAdminSearchCoachesResponse,
)
from app.services import org_admin_invite_coach as org_admin_invite_coach_service

router = APIRouter(prefix="/admin", tags=["org-admin-invite-coach"])

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

INVITE_VALIDATION_ERROR_RESPONSES = {
    400: openapi_error_examples(
        "Missing or invalid invite coach fields",
        examples={
            "empty_email": {
                "code": "VALIDATION_ERROR",
                "message": "Email is required",
                "details": [{"field": "email", "message": "Email is required"}],
            },
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

INVITE_CONFLICT_ERROR_RESPONSE = {
    409: openapi_error(
        "Email already registered to a coach or user account",
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


@router.post(
    "/invite-coach",
    response_model=OrgAdminInviteCoachResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="inviteOrgAdminCoach",
    summary="Invite a coach by email",
    description=(
        "Invite a coach to the authenticated organization admin's organization "
        "from the **Invite Coach** screen (HE-363).\n\n"
        "Accepts Figma fields `email`, `phone`, and `company`. Metadata fields "
        "`phone` and `company` are accepted for client compatibility but are not "
        "persisted.\n\n"
        "Creates a pending coach record and sends an invitation email when email "
        "delivery is configured.\n\n"
        "Returns **201** on success.\n\n"
        "Returns **400** when the email is empty or invalid.\n\n"
        "Returns **409** when the email is already registered.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **INVITE_VALIDATION_ERROR_RESPONSES,
        **INVITE_CONFLICT_ERROR_RESPONSE,
        503: openapi_error(
            "Coaches table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Coach invitation is temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def invite_org_admin_coach(
    body: OrgAdminInviteCoachRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminInviteCoachResponse:
    """Invite a coach using their email address."""
    result = await org_admin_invite_coach_service.invite_coach(db, current_user, body)
    return OrgAdminInviteCoachResponse(**result)


@router.get(
    "/search-coaches",
    response_model=OrgAdminSearchCoachesResponse,
    operation_id="searchOrgAdminCoaches",
    summary="Search organization coaches",
    description=(
        "Search coaches in the authenticated organization admin's organization "
        "for the **Invite Coach** screen (HE-363).\n\n"
        "Accepts optional query parameter `search_query` to filter by coach name "
        "or email. Optional `phone` and `company` are client metadata and are not "
        "used for filtering.\n\n"
        "Returns coach `name`, `email`, and invitation `status` (`invited` or "
        "`active`) for each match.\n\n"
        "When `search_query` is omitted or blank, all coaches in the organization "
        "are returned.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        503: openapi_error(
            "Coaches table unavailable",
            code="CLIENT_TABLE_UNAVAILABLE",
            message="Coach invitation is temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def search_org_admin_coaches(
    search_query: str | None = Query(
        default=None,
        description="Search text matching coach name or email",
        examples=["Ava"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not used for search)",
        examples=["+1-555-0100"],
    ),
    company: str | None = Query(
        default=None,
        description="Optional client metadata from the Figma company field (not used for search)",
        examples=["Acme Realty"],
    ),
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminSearchCoachesResponse:
    """Search coaches based on the Invite Coach screen query."""
    _ = phone, company
    result = await org_admin_invite_coach_service.search_coaches(
        db,
        current_user,
        search_query=search_query,
    )
    return OrgAdminSearchCoachesResponse(**result)
