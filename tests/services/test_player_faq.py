"""Unit tests for player FAQs service helpers."""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

import pytest

from app.core.exceptions import AppException
from app.services import faq as faq_service


def test_build_player_faqs_payload_includes_player_questions() -> None:
    payload = faq_service.build_player_faqs_payload()
    assert payload["status"] == "ready"
    assert payload["title"] == "How can we help you?"
    assert "joining sessions" in payload["description"]
    questions = {item["question"] for item in payload["faqs"]}
    assert "How do I join a training session?" in questions
    assert "How do I view my assigned drills?" in questions


def test_get_faq_by_id_returns_item() -> None:
    payload = faq_service.build_player_faqs_payload()
    faq_id = payload["faqs"][0]["id"]
    detail = faq_service.get_faq_by_id(faq_id, profile="player")
    assert detail["id"] == faq_id
    assert detail["question"]
    assert detail["answer"]


def test_get_faq_by_id_invalid_raises_404() -> None:
    with pytest.raises(AppException) as exc_info:
        faq_service.get_faq_by_id(
            UUID("00000000-0000-4000-8000-000000000099"),
            profile="player",
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "FAQ_NOT_FOUND"


def test_build_player_faqs_payload_empty_state() -> None:
    with patch("app.services.faq.get_player_faq_articles", return_value=[]):
        payload = faq_service.build_player_faqs_payload()
    assert payload["status"] == "empty"
    assert payload["faqs"] == []
