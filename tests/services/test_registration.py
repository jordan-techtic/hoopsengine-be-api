"""Unit tests for coach registration service."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.services.registration import register_coach, validate_username
from tests.conftest import (
    TEST_MISMATCH_CONFIRM_PASSWORD,
    TEST_PLACEHOLDER_HASH,
    TEST_VALID_PASSWORD,
    TEST_WEAK_PASSWORD_LONG,
)


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "John",
        "last_name": "Doe",
        "username": "johndoe",
        "email": "john.doe@example.com",
        "password": TEST_VALID_PASSWORD,
        "confirm_password": TEST_VALID_PASSWORD,
        "terms_accepted": True,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_validate_username_rejects_invalid_characters() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_username("john-doe!")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_username_accepts_alphanumeric_underscore() -> None:
    assert validate_username("john_doe123") == "john_doe123"


def test_register_rejects_terms_false() -> None:
    async def _run() -> None:
        db = AsyncMock()
        await register_coach(db, **_valid_kwargs(terms_accepted=False))

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "terms_accepted"


def test_register_rejects_password_mismatch() -> None:
    async def _run() -> None:
        db = AsyncMock()
        await register_coach(
            db,
            **_valid_kwargs(confirm_password=TEST_MISMATCH_CONFIRM_PASSWORD),
        )

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "confirm_password"


def test_register_rejects_weak_password() -> None:
    async def _run() -> None:
        db = AsyncMock()
        await register_coach(
            db,
            **_valid_kwargs(
                password=TEST_WEAK_PASSWORD_LONG,
                confirm_password=TEST_WEAK_PASSWORD_LONG,
            ),
        )

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_register_rejects_empty_first_name() -> None:
    async def _run() -> None:
        db = AsyncMock()
        await register_coach(db, **_valid_kwargs(first_name="   "))

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "first_name"


@patch("app.services.registration.send_verification_email")
@patch("app.services.registration.auth_service.get_user_by_email", new_callable=AsyncMock)
@patch("app.services.registration.get_user_by_username", new_callable=AsyncMock)
def test_register_duplicate_email_raises_409(
    mock_get_username: AsyncMock,
    mock_get_email: AsyncMock,
    _mock_send_email: MagicMock,
) -> None:
    mock_get_email.return_value = User(
        id=uuid4(),
        email="john.doe@example.com",
        encrypted_password=TEST_PLACEHOLDER_HASH,
        role=UserRole.COACH.value,
        is_super_admin=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    mock_get_username.return_value = None

    async def _run() -> None:
        db = AsyncMock()
        await register_coach(db, **_valid_kwargs())

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "EMAIL_ALREADY_IN_USE"


@patch("app.services.registration.send_verification_email")
@patch("app.services.registration.auth_service.get_user_by_email", new_callable=AsyncMock)
@patch("app.services.registration.get_user_by_username", new_callable=AsyncMock)
def test_register_duplicate_username_raises_409(
    mock_get_username: AsyncMock,
    mock_get_email: AsyncMock,
    _mock_send_email: MagicMock,
) -> None:
    mock_get_email.return_value = None
    mock_get_username.return_value = User(
        id=uuid4(),
        email="other@example.com",
        username="johndoe",
        encrypted_password=TEST_PLACEHOLDER_HASH,
        role=UserRole.COACH.value,
        is_super_admin=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    async def _run() -> None:
        db = AsyncMock()
        await register_coach(db, **_valid_kwargs())

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "USERNAME_ALREADY_IN_USE"
