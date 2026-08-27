"""Unit tests for roster search validation."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.roster import _validate_search_query


def test_validate_search_query_rejects_empty() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_search_query("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_search_query_returns_trimmed_value() -> None:
    assert _validate_search_query("  jane  ") == "jane"
