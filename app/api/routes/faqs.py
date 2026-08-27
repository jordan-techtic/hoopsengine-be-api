"""Public FAQs endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.errors import openapi_error
from app.schemas.faq import FaqsListResponse
from app.services import faq as faq_service
from app.services.account_settings import validate_numeric_phone

router = APIRouter(prefix="/faqs", tags=["faqs"])

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Invalid optional query parameters",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "phone", "message": "Phone number must contain 10 to 15 digits"}],
    ),
    422: openapi_error(
        "Request query failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}


@router.get(
    "",
    response_model=FaqsListResponse,
    operation_id="getFaqs",
    summary="Retrieve FAQs",
    description=(
        "Return the FAQ list for the **FAQs** screen, including intro banner copy, "
        "expandable question/answer rows, and support `phone` for the Contact Support card.\n\n"
        "Returns **200** with an empty `faqs` array when no articles are configured "
        "(empty state — not an error).\n\n"
        "Optional query parameter `phone` may be supplied for client-side validation "
        "before navigating to Contact Support; invalid values return **400**.\n\n"
        "**Public endpoint — no authentication required.**"
    ),
    responses={
        **VALIDATION_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_faqs(
    phone: str | None = Query(
        default=None,
        description=(
            "Optional client phone value to validate before opening Contact Support "
            "(10–15 digits, formatting allowed)"
        ),
        examples=["+15558392001"],
    ),
) -> FaqsListResponse:
    if phone is not None and phone.strip():
        validate_numeric_phone(phone)
    payload = faq_service.build_faqs_payload()
    return FaqsListResponse(**payload)
