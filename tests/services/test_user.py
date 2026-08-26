import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import AppException
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import AdminUserCreateRequest, normalize_role_value
from app.services.user import (
    build_pagination_meta,
    delete_user,
    display_name,
    to_item,
    validate_password,
)


def _user(**overrides: object) -> User:
    values = {
        "id": uuid4(),
        "email": "john.doe@example.com",
        "encrypted_password": "hashed",
        "role": UserRole.COACH.value,
        "first_name": "John",
        "last_name": "Doe",
        "is_super_admin": False,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return User(**values)


def test_to_item_omits_password_and_builds_name() -> None:
    item = to_item(_user(), current_user_id=uuid4())
    assert item.name == "John Doe"
    assert item.email == "john.doe@example.com"
    assert item.role == UserRole.COACH
    assert item.roles == ["coach"]
    assert item.description is None
    assert item.is_self is False
    assert not hasattr(item, "password")
    dumped = item.model_dump()
    assert "encrypted_password" not in dumped
    assert "password" not in dumped


def test_to_item_marks_self() -> None:
    user = _user()
    item = to_item(user, current_user_id=user.id)
    assert item.is_self is True


def test_display_name_falls_back_to_email() -> None:
    user = _user(first_name=None, last_name=None)
    assert display_name(user) == "john.doe@example.com"


def test_validate_password_rejects_example_ticket_password() -> None:
    with pytest.raises(AppException) as exc_info:
        validate_password("password123")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_password_accepts_complex_password() -> None:
    assert validate_password("Coach@123") == "Coach@123"


def test_normalize_role_accepts_display_label() -> None:
    assert normalize_role_value("Coach") == UserRole.COACH
    assert normalize_role_value("Player") == UserRole.PLAYER


def test_create_schema_coerces_coach_label() -> None:
    payload = AdminUserCreateRequest.model_validate(
        {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "password": "Coach@123",
            "role": "Coach",
        }
    )
    assert payload.role == UserRole.COACH


def test_build_pagination_meta_empty() -> None:
    meta = build_pagination_meta(total=0, page=1, page_size=20)
    assert meta["total"] == 0
    assert meta["has_next"] is False


def test_delete_own_account_400() -> None:
    user_id = uuid4()

    async def _run() -> None:
        await delete_user(AsyncMock(), user_id, current_user_id=user_id)

    with pytest.raises(AppException) as exc_info:
        asyncio.run(_run())
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "CANNOT_DELETE_SELF"
