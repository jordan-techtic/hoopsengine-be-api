"""Unit tests for organization admin change-password service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import AppException
from app.core.security import hash_password
from app.models.user import User
from app.schemas.org_admin_change_password import OrgAdminChangePasswordRequest
from app.services import org_admin_profile as org_admin_profile_service
from tests.conftest import (
    TEST_DIFFERENT_PASSWORD,
    TEST_INVALID_PASSWORD,
    TEST_NEW_SECURE_PASSWORD,
    TEST_VALID_PASSWORD,
)


def _org_admin_user(password: str = TEST_VALID_PASSWORD) -> User:
    return User(
        email="orgadmin@example.com",
        encrypted_password=hash_password(password),
        role="org_admin",
        is_super_admin=False,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_change_org_admin_password_delegates_to_account_settings() -> None:
    db = AsyncMock()
    user = _org_admin_user(TEST_VALID_PASSWORD)
    payload = OrgAdminChangePasswordRequest(
        current_password=TEST_VALID_PASSWORD,
        new_password=TEST_NEW_SECURE_PASSWORD,
        confirm_password=TEST_NEW_SECURE_PASSWORD,
    )

    with patch(
        "app.services.org_admin_profile.account_settings_service.change_password",
        new_callable=AsyncMock,
        return_value=user,
    ) as change_password_mock:
        result = await org_admin_profile_service.change_org_admin_password(db, user, payload)

    assert result is user
    change_password_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_change_org_admin_password_mismatch_raises_400() -> None:
    db = AsyncMock()
    user = _org_admin_user(TEST_VALID_PASSWORD)
    payload = OrgAdminChangePasswordRequest(
        current_password=TEST_VALID_PASSWORD,
        new_password=TEST_NEW_SECURE_PASSWORD,
        confirm_password=TEST_DIFFERENT_PASSWORD,
    )

    with pytest.raises(AppException) as exc_info:
        await org_admin_profile_service.change_org_admin_password(db, user, payload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.details[0]["field"] == "confirm_password"


@pytest.mark.asyncio
async def test_change_org_admin_password_wrong_current_raises_400() -> None:
    db = AsyncMock()
    user = _org_admin_user(TEST_VALID_PASSWORD)
    payload = OrgAdminChangePasswordRequest(
        current_password=TEST_INVALID_PASSWORD,
        new_password=TEST_NEW_SECURE_PASSWORD,
        confirm_password=TEST_NEW_SECURE_PASSWORD,
    )

    with pytest.raises(AppException) as exc_info:
        await org_admin_profile_service.change_org_admin_password(db, user, payload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
