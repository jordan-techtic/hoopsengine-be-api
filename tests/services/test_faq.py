"""Unit tests for FAQs service."""

from __future__ import annotations

from unittest.mock import patch

from app.services import faq as faq_service


def test_build_faqs_payload_includes_questions_and_answers() -> None:
    payload = faq_service.build_faqs_payload()
    assert payload["success"] is True
    assert payload["status"] == "ready"
    assert payload["title"] == "How can we help you?"
    assert payload["phone"]
    assert payload["link"] == "/api/v1/support/contact"
    assert payload["faqs"]
    assert payload["faqs"][0]["question"]
    assert payload["faqs"][0]["answer"]
    assert payload["faqs"][0]["id"]


def test_build_faqs_payload_empty_state() -> None:
    with patch("app.services.faq.get_help_articles", return_value=[]):
        payload = faq_service.build_faqs_payload()
    assert payload["status"] == "empty"
    assert payload["faqs"] == []
    assert payload["message"] == "No FAQs are available at this time"


def test_build_faqs_payload_skips_incomplete_articles() -> None:
    with patch(
        "app.services.faq.get_help_articles",
        return_value=[
            {"question": "Valid?", "answer": "Yes."},
            {"question": "", "answer": "Missing question"},
            {"question": "Missing answer", "answer": ""},
        ],
    ):
        payload = faq_service.build_faqs_payload()
    assert len(payload["faqs"]) == 1
    assert payload["faqs"][0]["question"] == "Valid?"
