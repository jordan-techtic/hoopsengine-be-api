"""Unit tests for coach queue helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.coach_queue import (
    _pending_title,
    _validate_item_type,
    _validate_queue_status,
    _validate_status_filter,
)


def test_pending_title_singular_and_plural() -> None:
    assert _pending_title(1) == "1 Item Pending Sync"
    assert _pending_title(3) == "3 Items Pending Sync"


def test_validate_status_filter_accepts_pending_sync() -> None:
    assert _validate_status_filter("pending_sync") == "pending_sync"


def test_validate_status_filter_rejects_invalid() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_status_filter("bad")
    assert exc_info.value.status_code == 400


def test_validate_item_type_accepts_session_data() -> None:
    assert _validate_item_type("session_data") == "session_data"


def test_validate_queue_status_accepts_synced() -> None:
    assert _validate_queue_status("synced") == "synced"
