"""Unit tests for player invitation code verification service."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services import player_invitation as player_invitation_service


def test_invitation_code_format_regex_accepts_valid_code() -> None:
    assert player_invitation_service.validate_invitation_code_format("PC-A1B2C3D4") == "PC-A1B2C3D4"


def test_validate_invitation_code_format_rejects_play_prefix() -> None:
    with pytest.raises(AppException) as exc_info:
        player_invitation_service.validate_invitation_code_format("PLAY-7492")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "invitation_code"


def test_validate_invitation_code_format_rejects_empty() -> None:
    with pytest.raises(AppException) as exc_info:
        player_invitation_service.validate_invitation_code_format("   ")
    assert exc_info.value.status_code == 400


def test_validate_invitation_code_format_rejects_lowercase() -> None:
    with pytest.raises(AppException) as exc_info:
        player_invitation_service.validate_invitation_code_format("pc-a1b2c3d4")
    assert exc_info.value.status_code == 400
