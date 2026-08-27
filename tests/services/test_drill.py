"""Unit tests for drill catalog validation and helpers."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.services.drill import (
    _resolve_search_term,
    _validate_drill_category,
    _validate_drill_name,
    _validate_search_query,
)


def test_validate_search_query_rejects_empty() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_search_query("   ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_validate_search_query_rejects_none() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_search_query(None)
    assert exc_info.value.status_code == 400


def test_validate_search_query_returns_trimmed_value() -> None:
    assert _validate_search_query("  warm  ") == "warm"


def test_validate_drill_name_rejects_empty() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_drill_name("")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "drill_name"


def test_validate_drill_category_rejects_empty() -> None:
    with pytest.raises(AppException) as exc_info:
        _validate_drill_category("  ")
    assert exc_info.value.status_code == 400
    assert exc_info.value.details[0]["field"] == "drill_category"


def test_resolve_search_term_prefers_search() -> None:
    assert _resolve_search_term(search="alpha", full_name="beta", q="gamma") == "alpha"


def test_resolve_search_term_uses_full_name_alias() -> None:
    assert _resolve_search_term(search=None, full_name="Jane", q=None) == "Jane"


def test_resolve_search_term_returns_none_when_all_empty() -> None:
    assert _resolve_search_term(search="", full_name=None, q="") is None
