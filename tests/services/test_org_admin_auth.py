"""Unit tests for organization admin auth service (HE-423)."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services import org_admin_auth as org_admin_auth_service


def test_resolve_login_identifier_prefers_email() -> None:
    identifier = org_admin_auth_service.resolve_login_identifier(
        email=" admin@test.com ",
        username="other",
    )
    assert identifier == "admin@test.com"


def test_resolve_login_identifier_missing_400() -> None:
    with pytest.raises(AppException) as exc_info:
        org_admin_auth_service.resolve_login_identifier(email=None, username="  ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "username"


def test_validate_login_password_empty_400() -> None:
    with pytest.raises(AppException) as exc_info:
        org_admin_auth_service.validate_login_password("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "password"


def test_validate_login_password_too_short_400() -> None:
    with pytest.raises(AppException) as exc_info:
        org_admin_auth_service.validate_login_password("short")
    assert exc_info.value.status_code == 400
    assert "8 characters" in exc_info.value.message


def test_validate_login_identifier_invalid_email_400() -> None:
    with pytest.raises(AppException) as exc_info:
        org_admin_auth_service.validate_login_identifier_format("not-an-email")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "email"
