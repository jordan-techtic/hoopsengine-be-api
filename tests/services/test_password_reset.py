"""Unit tests for authenticated password reset service (HE-298)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AppException
from app.core.security import hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.services import password_reset as password_reset_service
from tests.conftest import (
    TEST_CURRENT_PASSWORD,
    TEST_NEW_SECURE_PASSWORD,
    TEST_DIFFERENT_PASSWORD,
    TEST_WEAK_PASSWORD,
    TEST_WEAK_PASSWORD_LONG,
    TEST_VALID_COMPLEX_PASSWORD,
)


def _user(*, encrypted_password: str | None = None) -> User:
    return User(
        id=MagicMock(),
        email="coach@test.com",
        encrypted_password=encrypted_password or hash_password(TEST_CURRENT_PASSWORD),
        role=UserRole.COACH.value,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_reset_password_success() -> None:
    user = _user()
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda u: u)

    result = await password_reset_service.reset_authenticated_password(
        db,
        user=user,
        new_password=TEST_NEW_SECURE_PASSWORD,
        confirm_password=TEST_NEW_SECURE_PASSWORD,
    )

    assert verify_password(TEST_NEW_SECURE_PASSWORD, result.encrypted_password) is True
    assert verify_password(TEST_CURRENT_PASSWORD, result.encrypted_password) is False
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_password_rejects_empty_new_password() -> None:
    user = _user()
    db = AsyncMock()

    with pytest.raises(AppException) as exc_info:
        await password_reset_service.reset_authenticated_password(
            db,
            user=user,
            new_password="",
            confirm_password=TEST_NEW_SECURE_PASSWORD,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_reset_password_rejects_mismatch() -> None:
    user = _user()
    db = AsyncMock()

    with pytest.raises(AppException) as exc_info:
        await password_reset_service.reset_authenticated_password(
            db,
            user=user,
            new_password=TEST_NEW_SECURE_PASSWORD,
            confirm_password=TEST_DIFFERENT_PASSWORD,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_reset_password_rejects_weak_password() -> None:
    user = _user()
    db = AsyncMock()

    with pytest.raises(AppException) as exc_info:
        await password_reset_service.reset_authenticated_password(
            db,
            user=user,
            new_password=TEST_WEAK_PASSWORD,
            confirm_password=TEST_WEAK_PASSWORD,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_reset_password_rejects_same_password() -> None:
    user = _user()
    db = AsyncMock()

    with pytest.raises(AppException) as exc_info:
        await password_reset_service.reset_authenticated_password(
            db,
            user=user,
            new_password=TEST_CURRENT_PASSWORD,
            confirm_password=TEST_CURRENT_PASSWORD,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "PASSWORD_UNCHANGED"


def test_validate_password_for_reset_requires_value() -> None:
    with pytest.raises(AppException) as exc_info:
        password_reset_service.validate_password_for_reset(None)

    assert exc_info.value.status_code == 400


def test_validate_password_for_reset_returns_requirements() -> None:
    requirements, is_valid = password_reset_service.validate_password_for_reset(
        TEST_VALID_COMPLEX_PASSWORD
    )
    assert is_valid is True
    assert requirements["min_length"] is True
    assert requirements["has_number"] is True
    assert requirements["has_special"] is True


def test_validate_password_for_reset_detects_weak_password() -> None:
    requirements, is_valid = password_reset_service.validate_password_for_reset(
        TEST_WEAK_PASSWORD_LONG
    )
    assert is_valid is False
    assert requirements["has_number"] is False
    assert requirements["has_special"] is False
