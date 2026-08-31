"""Unit tests for organization admin profile service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.org_admin_profile import validate_contact_info, validate_organization_description


def test_validate_organization_description_success() -> None:
    assert validate_organization_description("  Youth academy  ") == "Youth academy"


def test_validate_organization_description_empty_400() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_organization_description("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.details[0]["field"] == "description"


def test_validate_contact_info_email_success() -> None:
    assert validate_contact_info("Contact@Example.com") == "contact@example.com"


def test_validate_contact_info_phone_success() -> None:
    assert validate_contact_info("+1 (555) 382-9102") == "+1 (555) 382-9102"


def test_validate_contact_info_invalid_400() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_contact_info("not-valid")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.details[0]["field"] == "contact_info"


def test_validate_contact_info_empty_400() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_contact_info("")
    assert exc_info.value.details[0]["field"] == "contact_info"
