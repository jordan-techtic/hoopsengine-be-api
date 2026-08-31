"""Business logic for public Contact Support JSON APIs."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.support_request import SupportRequest
from app.schemas.support_contact import SupportContactCreateRequest
from app.services.account_settings import (
    get_support_contact_info,
    validate_numeric_phone,
    validate_support_message,
    validate_support_subject,
)

logger = logging.getLogger(__name__)


def _validate_email(email: str) -> str:
    """Return a normalized email or raise 400 when invalid."""
    cleaned = (email or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Email is required",
            status_code=400,
            details=[{"field": "email", "message": "Email is required"}],
        )
    try:
        return str(TypeAdapter(EmailStr).validate_python(cleaned)).strip().lower()
    except ValidationError as exc:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid email address",
            status_code=400,
            details=[{"field": "email", "message": "Enter a valid email address"}],
        ) from exc


def validate_contact_payload(payload: SupportContactCreateRequest) -> tuple[str, str, str, str]:
    """Validate contact support fields and return normalized values."""
    email = _validate_email(payload.email)
    phone = validate_numeric_phone(payload.phone)
    subject = validate_support_subject(payload.inquiry_subject)
    message = validate_support_message(payload.message_description)
    return email, phone, subject, message


async def check_duplicate_submission(
    db: AsyncSession,
    *,
    email: str,
    subject: str,
    message: str,
) -> None:
    """Raise 409 when an identical submission was received recently."""
    window_start = datetime.now(timezone.utc) - timedelta(
        seconds=settings.SUPPORT_DUPLICATE_WINDOW_SECONDS
    )
    result = await db.execute(
        select(SupportRequest.id).where(
            SupportRequest.email == email,
            SupportRequest.subject == subject,
            SupportRequest.message == message,
            SupportRequest.created_at >= window_start,
        ).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        raise AppException(
            code="DUPLICATE_SUPPORT_SUBMISSION",
            message="A similar support message was recently submitted. Please wait before submitting again.",
            status_code=409,
            details=[
                {
                    "field": "message_description",
                    "message": "A similar support message was recently submitted",
                }
            ],
        )


def _display_name_from_email(email: str) -> str:
    local = email.split("@", 1)[0].strip()
    return local.replace(".", " ").replace("_", " ").title() or "Support Contact"


async def create_contact_request(
    db: AsyncSession,
    payload: SupportContactCreateRequest,
) -> dict[str, object]:
    """Persist a public support contact submission."""
    email, phone, subject, message = validate_contact_payload(payload)
    await check_duplicate_submission(db, email=email, subject=subject, message=message)

    support_request = SupportRequest(
        email=email,
        name=_display_name_from_email(email),
        subject=subject,
        message=message,
        phone=phone,
    )
    db.add(support_request)
    await db.commit()
    await db.refresh(support_request)
    logger.info("Public support contact submitted: %s", support_request.id)

    return {
        "success": True,
        "message": "Your support request has been submitted successfully",
        "status": "submitted",
        "description": "We typically respond within 24 hours",
        "link": None,
        "error": None,
        "id": support_request.id,
        "request_id": support_request.id,
        "email": email,
        "phone": phone,
    }


def get_contact_info() -> dict[str, object]:
    """Return configured public support contact information."""
    contact = get_support_contact_info()
    return {
        "success": True,
        "message": "Support contact information loaded successfully",
        "status": "ready",
        "description": "Contact our support team by email or phone",
        "link": None,
        "error": None,
        "id": None,
        "email": contact["email"],
        "phone": contact["phone"],
    }


def get_player_contact_info() -> dict[str, object]:
    """Return player Contact Support directory details including hours and live chat."""
    base = get_contact_info()
    address = settings.SUPPORT_CONTACT_ADDRESS.strip() or None
    support_name = "Support Team"
    email = str(base["email"])
    phone = str(base["phone"])
    return {
        **base,
        "name": support_name,
        "address": address,
        "profile": {
            "name": support_name,
            "email": email,
            "phone": phone,
        },
        "avatar": None,
        "operating_hours": settings.SUPPORT_OPERATING_HOURS,
        "live_chat_label": settings.SUPPORT_LIVE_CHAT_LABEL,
    }
