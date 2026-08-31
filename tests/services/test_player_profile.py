"""Unit tests for player profile service."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.enums import UserRole
from app.models.user import User
from app.services import player_profile as player_profile_service


def _player_user(**overrides: object) -> User:
    now = datetime.now(timezone.utc)
    values: dict[str, object] = {
        "id": uuid4(),
        "email": "player@example.com",
        "username": "playeruser",
        "encrypted_password": "$2b$12$test",
        "role": UserRole.PLAYER.value,
        "first_name": "Viewer",
        "last_name": "Player",
        "is_super_admin": False,
        "is_active": True,
        "email_confirmed_at": now,
        "created_at": now,
    }
    values.update(overrides)
    return User(**values)


def test_build_player_profile_response_includes_frontend_fields() -> None:
    user = _player_user(phone="+1 (555) 382-9102")
    result = player_profile_service.build_player_profile_response(
        user,
        message="Profile loaded successfully",
        description="Review and update your personal information",
    )
    assert result["success"] is True
    assert result["title"] == "Edit Profile"
    assert result["name"] == "Viewer Player"
    assert result["first_name"] == "Viewer"
    assert result["last_name"] == "Player"
    assert result["email"] == "player@example.com"
    assert result["phone_number"] == "+1 (555) 382-9102"
    assert result["profile"]["email"] == "player@example.com"
