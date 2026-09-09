"""Business logic for organization admin Contact Support APIs (HE-413)."""

from __future__ import annotations

import logging
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.support_request import SupportRequest
from app.models.user import User
from app.schemas.org_admin_support import OrgAdminSupportContactRequest
from app.schemas.support_contact import SupportContactCreateRequest
from app.services import support_contact as support_contact_service

logger = logging.getLogger(__name__)

CONFIRMATION_MESSAGE = "Your support request has been submitted successfully"
CONFIRMATION_DESCRIPTION = "We typically respond within 24 hours"
ORGANIZATION_NAME = "Hoops Engine"


def _validate_optional_phone(phone: str | None) -> None:
    """Validate optional Figma status-bar phone metadata when provided."""
    if phone is None or not phone.strip():
        return
    cleaned = phone.strip()
    if len(cleaned) > 30:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number is invalid",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number is invalid"}],
        )
    if not re.sub(r"\D", "", cleaned):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Phone number must contain at least one digit",
            status_code=400,
            details=[{"field": "phone", "message": "Phone number must contain at least one digit"}],
        )


def _support_address() -> str | None:
    """Return configured support address when present."""
    cleaned = settings.SUPPORT_CONTACT_ADDRESS.strip()
    return cleaned or None


def _enrich_submission_result(result: dict[str, object]) -> dict[str, object]:
    """Add org-admin Contact Support response fields to a submission payload."""
    phone_value = str(result["phone"])
    return {
        **result,
        "organization": ORGANIZATION_NAME,
        "phone_number": phone_value,
        "address": _support_address(),
    }


async def submit_contact_inquiry(
    db: AsyncSession,
    payload: OrgAdminSupportContactRequest,
) -> dict[str, object]:
    """Persist an organization admin support inquiry using shared validation."""
    service_payload = SupportContactCreateRequest(**payload.model_dump())
    result = await support_contact_service.create_contact_request(db, service_payload)
    logger.info("Org admin support contact submitted: %s", result["id"])
    return _enrich_submission_result(result)


async def get_contact_confirmation(
    db: AsyncSession,
    *,
    user: User | None = None,
    request_id: UUID | None = None,
    phone: str | None = None,
) -> dict[str, object]:
    """Return confirmation details for a submitted support inquiry."""
    _validate_optional_phone(phone)
    directory = support_contact_service.get_player_contact_info()
    address = _support_address()

    if request_id is None:
        return {
            "success": True,
            "message": CONFIRMATION_MESSAGE,
            "status": "confirmed",
            "description": CONFIRMATION_DESCRIPTION,
            "link": None,
            "error": None,
            "organization": ORGANIZATION_NAME,
            "id": None,
            "email": directory["email"],
            "phone": directory["phone"],
            "phone_number": directory["phone"],
            "address": address,
            "inquiry_subject": None,
            "message_description": None,
            "operating_hours": directory["operating_hours"],
            "live_chat_label": directory["live_chat_label"],
            "profile": directory["profile"],
            "avatar": directory["avatar"],
        }

    if user is None:
        raise AppException(
            code="FORBIDDEN",
            message="You do not have permission to access this resource",
            status_code=403,
        )

    result = await db.execute(
        select(SupportRequest).where(SupportRequest.id == request_id).limit(1)
    )
    support_request = result.scalar_one_or_none()
    if support_request is None:
        raise AppException(
            code="SUPPORT_REQUEST_NOT_FOUND",
            message="Support inquiry not found",
            status_code=404,
            details=[{"field": "request_id", "message": "Support inquiry not found"}],
        )

    submitted_phone = support_request.phone or str(directory["phone"])
    return {
        "success": True,
        "message": CONFIRMATION_MESSAGE,
        "status": "confirmed",
        "description": CONFIRMATION_DESCRIPTION,
        "link": None,
        "error": None,
        "organization": ORGANIZATION_NAME,
        "id": support_request.id,
        "email": support_request.email,
        "phone": submitted_phone,
        "phone_number": submitted_phone,
        "address": address,
        "inquiry_subject": support_request.subject,
        "message_description": support_request.message,
        "operating_hours": directory["operating_hours"],
        "live_chat_label": directory["live_chat_label"],
        "profile": directory["profile"],
        "avatar": directory["avatar"],
    }
