"""Unit tests for session mode helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.models.enums import SessionMode
from app.services import session_record as session_record_service


def test_get_session_modes_returns_three_modes() -> None:
    modes = session_record_service.get_session_modes()
    assert len(modes) == 3
    assert {item.mode for item in modes} == {
        SessionMode.ONE_DRILL,
        SessionMode.DAILY_OPTIONS,
        SessionMode.PRACTICE_PLAN,
    }


def test_get_mode_or_404_valid() -> None:
    item = session_record_service.get_mode_or_404("one_drill")
    assert item.mode == SessionMode.ONE_DRILL
    assert item.label == "One Drill"


def test_get_mode_or_404_invalid() -> None:
    with pytest.raises(AppException) as exc_info:
        session_record_service.get_mode_or_404("not_a_mode")
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "SESSION_MODE_NOT_FOUND"
