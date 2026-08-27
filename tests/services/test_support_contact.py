"""Unit tests for public Contact Support validation."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.schemas.support_contact import SupportContactCreateRequest
from app.services.support_contact import validate_contact_payload


def test_validate_contact_payload_success() -> None:
    payload = SupportContactCreateRequest(
        email="user@example.com",
        phone="+15558392001",
        inquiry_subject="Technical Issue",
        message_description="Need help with login.",
    )
    email, phone, subject, message = validate_contact_payload(payload)
    assert email == "user@example.com"
    assert phone == "15558392001"
    assert subject == "Technical Issue"
    assert message == "Need help with login."


def test_validate_contact_payload_invalid_email_400() -> None:
    payload = SupportContactCreateRequest(
        email="bad-email",
        phone="+15558392001",
        inquiry_subject="Technical Issue",
        message_description="Help",
    )
    with pytest.raises(AppException) as exc_info:
        validate_contact_payload(payload)
    assert exc_info.value.status_code == 400


def test_validate_contact_payload_invalid_phone_400() -> None:
    payload = SupportContactCreateRequest(
        email="user@example.com",
        phone="letters-only",
        inquiry_subject="Technical Issue",
        message_description="Help",
    )
    with pytest.raises(AppException) as exc_info:
        validate_contact_payload(payload)
    assert exc_info.value.status_code == 400


def test_validate_contact_payload_invalid_subject_409() -> None:
    payload = SupportContactCreateRequest(
        email="user@example.com",
        phone="+15558392001",
        inquiry_subject="Unknown Subject",
        message_description="Help",
    )
    with pytest.raises(AppException) as exc_info:
        validate_contact_payload(payload)
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_INQUIRY_SUBJECT"


def test_validate_contact_payload_message_too_long_400() -> None:
    payload = SupportContactCreateRequest(
        email="user@example.com",
        phone="+15558392001",
        inquiry_subject="Technical Issue",
        message_description="x" * 501,
    )
    with pytest.raises(AppException) as exc_info:
        validate_contact_payload(payload)
    assert exc_info.value.status_code == 400
