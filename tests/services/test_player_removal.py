"""Unit tests for player removal helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.schemas.player_removal import REMOVAL_CONFIRMATION_MESSAGE
from app.services.player_removal import (
    _phones_match,
    _preview_fields_valid,
    _validate_removal_email,
    get_removal_confirmation,
)


def test_get_removal_confirmation_message() -> None:
    result = get_removal_confirmation()
    assert result["confirmation_message"] == REMOVAL_CONFIRMATION_MESSAGE
    assert result["description"] == REMOVAL_CONFIRMATION_MESSAGE
    assert result["can_remove"] is False


def test_preview_fields_valid_when_all_present() -> None:
    assert _preview_fields_valid(
        full_name="Jane Doe",
        email="jane@example.com",
        phone="(555) 123-4567",
    )


def test_preview_fields_invalid_when_email_empty() -> None:
    assert not _preview_fields_valid(
        full_name="Jane Doe",
        email="",
        phone="(555) 123-4567",
    )


def test_validate_removal_email_empty_400() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_removal_email("")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_phones_match_with_formatting_differences() -> None:
    assert _phones_match("+1 (555) 123-4567", "5551234567")
    assert _phones_match("5551234567", "15551234567")
    assert not _phones_match("+15559876543", "5551234567")
