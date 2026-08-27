"""Unit tests for attendance service helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.attendance import (
    ATTENDANCE_STATUS_ABSENT,
    ATTENDANCE_STATUS_PRESENT,
    _summary_counts,
    _sync_attendance_statuses,
    resolve_attendance_search_text,
)


def test_resolve_attendance_search_text_accepts_full_name() -> None:
    assert resolve_attendance_search_text(search_query=None, full_name="Alex") == "Alex"


def test_resolve_attendance_search_text_empty_400() -> None:
    with pytest.raises(AppException) as exc_info:
        resolve_attendance_search_text(search_query=None, full_name="   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "full_name"


def test_summary_counts_present_players() -> None:
    players = [
        {"status": ATTENDANCE_STATUS_PRESENT},
        {"status": ATTENDANCE_STATUS_PRESENT},
        {"status": ATTENDANCE_STATUS_ABSENT},
    ]
    assert _summary_counts(players) == {"present_count": 2, "total_count": 3}


def test_sync_attendance_statuses_defaults_absent() -> None:
    roster = [{"id": "00000000-0000-4000-8000-000000000033"}]
    synced = _sync_attendance_statuses(roster, {})
    assert synced["00000000-0000-4000-8000-000000000033"] == ATTENDANCE_STATUS_ABSENT
