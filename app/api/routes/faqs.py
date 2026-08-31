"""Public FAQs endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.faq import (
    FaqContactSupportRequest,
    FaqContactSupportResponse,
    FaqDetailResponse,
    FaqsListResponse,
)
from app.schemas.support_contact import SupportContactCreateRequest
from app.services import faq as faq_service
from app.services import support_contact as support_contact_service
from app.services.account_settings import validate_numeric_phone

router = APIRouter(prefix="/faqs", tags=["faqs"])

FAQ_ID_PATH = Path(
    ...,
    description="Stable FAQ item UUID",
    examples=["6ba7b811-9dad-11d1-80b4-00c04fd430c8"],
)

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Invalid optional query parameters or contact-support fields",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "phone", "message": "Phone number must contain 10 to 15 digits"}],
    ),
    422: openapi_error(
        "Request query or body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

NOT_FOUND_ERROR_RESPONSES = {
    404: openapi_error(
        "FAQ item not found",
        code="FAQ_NOT_FOUND",
        message="FAQ not found",
    ),
}

CONFLICT_ERROR_RESPONSES = {
    409: openapi_error_examples(
        "Invalid inquiry subject or duplicate support submission",
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


def _validate_optional_phone(phone: str | None) -> None:
    if phone is not None and phone.strip():
        validate_numeric_phone(phone)


@router.get(
    "",
    response_model=FaqsListResponse,
    operation_id="getFaqs",
    summary="Retrieve FAQs",
    description=(
        "Return the FAQ list for the **FAQs** screen, including intro banner copy, "
        "expandable question/answer rows, and support `phone` for the Contact Support card.\n\n"
        "Use `profile=player` for player-module FAQs; omit or set `profile=coach` for "
        "coach help articles.\n\n"
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
    profile: str = Query(
        default="player",
        description="FAQ audience: player (default) or coach",
        examples=["player"],
    ),
    phone: str | None = Query(
        default=None,
        description=(
            "Optional client phone value to validate before opening Contact Support "
            "(10–15 digits, formatting allowed)"
        ),
        examples=["+1-555-0100"],
    ),
) -> FaqsListResponse:
    _validate_optional_phone(phone)
    normalized_profile = profile.strip().lower()
    if normalized_profile == "coach":
        payload = faq_service.build_faqs_payload()
    else:
        payload = faq_service.build_player_faqs_payload()
    return FaqsListResponse(**payload)


@router.get(
    "/{faq_id}",
    response_model=FaqDetailResponse,
    operation_id="getFaqById",
    summary="Retrieve a single FAQ by ID",
    description=(
        "Return one FAQ question and answer for the **FAQs** detail view.\n\n"
        "Use `profile=player` (default) or `profile=coach` to select the FAQ catalog.\n\n"
        "Returns **404** when the FAQ identifier does not match any configured article.\n\n"
        "**Public endpoint — no authentication required.**"
    ),
    responses={
        **NOT_FOUND_ERROR_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_faq_by_id(
    faq_id: UUID = FAQ_ID_PATH,
    profile: str = Query(
        default="player",
        description="FAQ audience: player (default) or coach",
        examples=["player"],
    ),
) -> FaqDetailResponse:
    normalized_profile = profile.strip().lower()
    audience = "coach" if normalized_profile == "coach" else "player"
    result = faq_service.get_faq_by_id(faq_id, profile=audience)
    return FaqDetailResponse(**result)


@router.post(
    "/contact-support",
    response_model=FaqContactSupportResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="contactSupportFromFaqs",
    summary="Contact support from FAQs",
    description=(
        "Submit a support inquiry from the **FAQs** screen Contact Support card.\n\n"
        "Required fields: `email`, `phone`, `inquiry_subject`, and `message_description` "
        "(max 500 characters).\n\n"
        "Returns **201** with a response commitment that the team typically responds "
        "within 24 hours.\n\n"
        "Returns **400** for missing fields, invalid email, non-numeric phone, or "
        "messages over 500 characters.\n\n"
        "Returns **409** when the inquiry subject is invalid or a duplicate submission "
        "is detected.\n\n"
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
async def contact_support_from_faqs(
    body: FaqContactSupportRequest,
    db: AsyncSession = Depends(get_db),
) -> FaqContactSupportResponse:
    service_payload = SupportContactCreateRequest(**body.model_dump())
    result = await support_contact_service.create_contact_request(db, service_payload)
    return FaqContactSupportResponse(
        message=str(result["message"]),
        description=str(result["description"]) if result.get("description") is not None else None,
        link=result.get("link") if isinstance(result.get("link"), str) else None,
        id=result["id"],  # type: ignore[arg-type]
        phone=str(result["phone"]),
    )
