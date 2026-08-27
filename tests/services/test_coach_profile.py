"""Unit tests for coach profile validation helpers."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.exceptions import AppException
from app.services.profile import (
    format_date_of_birth,
    parse_date_of_birth,
    validate_profile_email,
)


def test_validate_profile_email_accepts_valid_address() -> None:
    assert validate_profile_email("Alex.Morgan@Academy.com") == "alex.morgan@academy.com"


def test_validate_profile_email_rejects_invalid_format() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_profile_email("not-an-email")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_parse_date_of_birth_accepts_mm_dd_yyyy() -> None:
    assert parse_date_of_birth("08/24/1992") == date(1992, 8, 24)


def test_parse_date_of_birth_rejects_invalid_format() -> None:
    with pytest.raises(AppException) as exc_info:
        parse_date_of_birth("1992-08-24")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "date_of_birth"


def test_format_date_of_birth() -> None:
    assert format_date_of_birth(date(1992, 8, 24)) == "08/24/1992"
