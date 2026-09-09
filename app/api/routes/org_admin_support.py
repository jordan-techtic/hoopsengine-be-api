"""Organization admin Contact Support endpoints (HE-413)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer_scheme, get_current_org_admin, get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_admin_support import (
    OrgAdminSupportConfirmationResponse,
    OrgAdminSupportContactRequest,
    OrgAdminSupportContactResponse,
)
from app.services import org_admin_support as org_admin_support_service

router = APIRouter(prefix="/admin/support/contact", tags=["org-admin-support"])

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
        "Missing or invalid contact support fields",
        examples={
            "missing_email": {
                "code": "VALIDATION_ERROR",
                "message": "Email is required",
                "details": [{"field": "email", "message": "Email is required"}],
            },
            "invalid_email": {
                "code": "VALIDATION_ERROR",
                "message": "Enter a valid email address",
                "details": [{"field": "email", "message": "Enter a valid email address"}],
            },
            "message_too_long": {
                "code": "VALIDATION_ERROR",
                "message": "Message must be 500 characters or fewer",
                "details": [
                    {
                        "field": "message_description",
                        "message": "Message must be 500 characters or fewer",
                    }
                ],
            },
            "invalid_phone": {
                "code": "VALIDATION_ERROR",
                "message": "Phone number must contain at least one digit",
                "details": [
                    {"field": "phone", "message": "Phone number must contain at least one digit"}
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

CONFLICT_ERROR_RESPONSES = {
    409: openapi_error_examples(
        "Invalid inquiry subject or duplicate submission",
        examples={
            "invalid_inquiry_subject": {
                "code": "INVALID_INQUIRY_SUBJECT",
                "message": "Inquiry subject must be selected from the predefined options",
                "details": [
                    {
                        "field": "inquiry_subject",
                        "message": "Inquiry subject must be selected from the predefined options",
                    }
                ],
            },
            "duplicate_submission": {
                "code": "DUPLICATE_SUPPORT_SUBMISSION",
                "message": "A similar support message was recently submitted. Please wait before submitting again.",
                "details": [
                    {
                        "field": "message_description",
                        "message": "A similar support message was recently submitted",
                    }
                ],
            },
        },
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "Support inquiry not found",
        code="SUPPORT_REQUEST_NOT_FOUND",
        message="Support inquiry not found",
        details=[{"field": "request_id", "message": "Support inquiry not found"}],
    ),
}


async def get_org_admin_for_stored_confirmation(
    request_id: UUID | None = Query(
        default=None,
        description="Support request UUID returned from POST /admin/support/contact",
        examples=["11111111-2222-3333-4444-555555555555"],
    ),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Require org-admin JWT when loading stored inquiry details by request_id."""
    if request_id is None:
        return None
    user = await get_current_user(credentials, db)
    return get_current_org_admin(user)


@router.post(
    "",
    response_model=OrgAdminSupportContactResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="submitOrgAdminSupportContact",
    summary="Submit an organization admin support inquiry",
    description=(
        "Submit a support inquiry from the Organization Admin **Contact Support** screen "
        "(HE-413).\n\n"
        "Required fields: `email`, `phone`, `inquiry_subject`, and `message_description` "
        "(max 500 characters).\n\n"
        "Returns **201** with a confirmation message and response commitment that the "
        "team typically responds within 24 hours.\n\n"
        "Returns **400** for missing fields, invalid email, non-numeric phone, or "
        "messages over 500 characters.\n\n"
        "Returns **409** when the inquiry subject is not a predefined option or when "
        "a duplicate submission is detected within the configured time window.\n\n"
        "**Public endpoint — no authentication required.**"
    ),
    responses={
        **VALIDATION_ERROR_RESPONSES,
        **CONFLICT_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def submit_org_admin_support_contact(
    body: OrgAdminSupportContactRequest,
    db: AsyncSession = Depends(get_db),
) -> OrgAdminSupportContactResponse:
    """Submit a support inquiry from the Organization Admin Contact Support screen."""
    result = await org_admin_support_service.submit_contact_inquiry(db, body)
    return OrgAdminSupportContactResponse(**result)


@router.get(
    "/confirmation",
    response_model=OrgAdminSupportConfirmationResponse,
    operation_id="getOrgAdminSupportContactConfirmation",
    summary="Get support inquiry submission confirmation",
    description=(
        "Return confirmation details for a submitted Organization Admin support inquiry "
        "(HE-413).\n\n"
        "When `request_id` is provided, returns the stored inquiry details "
        "(`email`, `inquiry_subject`, `message_description`, `phone`) plus support "
        "directory metadata. **Requires authenticated organization admin JWT.**\n\n"
        "When `request_id` is omitted, returns the default confirmation copy and "
        "support directory contact details without authentication.\n\n"
        "Optional query parameter `phone` is client metadata and is not persisted.\n\n"
        "Returns **404** when `request_id` does not match a stored inquiry."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_org_admin_support_contact_confirmation(
    request_id: UUID | None = Query(
        default=None,
        description="Support request UUID returned from POST /admin/support/contact",
        examples=["11111111-2222-3333-4444-555555555555"],
    ),
    phone: str | None = Query(
        default=None,
        description="Optional client metadata from the status bar (not persisted)",
        examples=["+1-555-0100"],
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_org_admin_for_stored_confirmation),
) -> OrgAdminSupportConfirmationResponse:
    """Return confirmation details for a submitted support inquiry."""
    result = await org_admin_support_service.get_contact_confirmation(
        db,
        user=current_user,
        request_id=request_id,
        phone=phone,
    )
    return OrgAdminSupportConfirmationResponse(**result)
