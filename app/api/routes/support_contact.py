"""Public Contact Support endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.support_contact import (
    SupportContactCreateRequest,
    SupportContactCreateResponse,
    SupportContactInfoResponse,
)
from app.services import support_contact as support_contact_service

router = APIRouter(prefix="/support/contact", tags=["support-contact"])

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Missing or invalid contact support fields",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "email", "message": "Enter a valid email address"}],
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


@router.post(
    "",
    response_model=SupportContactCreateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="submitSupportContact",
    summary="Submit a support message",
    description=(
        "Submit a support inquiry from the **Contact Support** screen.\n\n"
        "Required fields: `email`, `phone`, `inquiry_subject`, and `message_description` "
        "(max 500 characters).\n\n"
        "Returns **201** with a response commitment that the team typically responds "
        "within 24 hours.\n\n"
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
async def submit_support_contact(
    body: SupportContactCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SupportContactCreateResponse:
    result = await support_contact_service.create_contact_request(db, body)
    return SupportContactCreateResponse(**result)


@router.get(
    "/info",
    response_model=SupportContactInfoResponse,
    operation_id="getSupportContactInfo",
    summary="Get support contact information",
    description=(
        "Return public support directory contact details for the **Contact Support** "
        "screen, including support `email` and `phone`.\n\n"
        "**Public endpoint — no authentication required.**"
    ),
    responses={
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_support_contact_info() -> SupportContactInfoResponse:
    result = support_contact_service.get_contact_info()
    return SupportContactInfoResponse(**result)
