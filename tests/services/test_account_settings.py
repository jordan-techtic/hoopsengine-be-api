"""Unit tests for account settings service."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.services import account_settings as account_settings_service


def test_split_full_name_two_parts() -> None:
    first, last = account_settings_service.split_full_name("Jane Doe")
    assert first == "Jane"
    assert last == "Doe"


def test_split_full_name_single_part() -> None:
    first, last = account_settings_service.split_full_name("Jane")
    assert first == "Jane"
    assert last == ""


def test_split_full_name_empty_raises() -> None:
    with pytest.raises(AppException) as exc_info:
        account_settings_service.split_full_name("   ")
    assert exc_info.value.status_code == 400


def test_validate_numeric_phone_accepts_digits() -> None:
    assert account_settings_service.validate_numeric_phone("+1 (555) 839-2001") == "15558392001"


def test_validate_numeric_phone_rejects_short() -> None:
    with pytest.raises(AppException) as exc_info:
        account_settings_service.validate_numeric_phone("123")
    assert exc_info.value.status_code == 400


def test_validate_support_subject_invalid_409() -> None:
    with pytest.raises(AppException) as exc_info:
        account_settings_service.validate_support_subject("Not A Real Subject")
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_INQUIRY_SUBJECT"


def test_validate_support_message_too_long_400() -> None:
    with pytest.raises(AppException) as exc_info:
        account_settings_service.validate_support_message("x" * 501)
    assert exc_info.value.status_code == 400


def test_can_enable_push_notifications_org_admin() -> None:
    user = User(
        email="admin@example.com",
        encrypted_password="hash",
        role=UserRole.ORG_ADMIN.value,
        is_super_admin=False,
        is_active=True,
    )
    assert account_settings_service.can_enable_push_notifications(user) is True


def test_can_enable_push_notifications_coach_false() -> None:
    user = User(
        email="coach@example.com",
        encrypted_password="hash",
        role=UserRole.COACH.value,
        is_super_admin=False,
        is_active=True,
    )
    assert account_settings_service.can_enable_push_notifications(user) is False


def test_get_help_articles_returns_defaults() -> None:
    articles = account_settings_service.get_help_articles()
    assert len(articles) >= 2
    assert "question" in articles[0]
    assert "answer" in articles[0]
