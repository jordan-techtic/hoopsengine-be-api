"""Integration tests for player FAQs API (HE-230)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import sync_engine

FAQS_BASE = "/api/v1/faqs"
FAQS_CONTACT_SUPPORT_BASE = "/api/v1/faqs/contact-support"

SUPPORT_PAYLOAD = {
    "email": "player.faq@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "Need help from the player FAQs screen.",
}


@pytest.fixture(autouse=True)
def _clean_support_requests() -> None:
    with sync_engine.begin() as connection:
        connection.execute(text("DELETE FROM support_requests_staging"))


def test_get_player_faqs_200(client: TestClient) -> None:
    response = client.get(FAQS_BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["title"] == "How can we help you?"
    assert "joining sessions" in body["description"]
    assert body["message"] == "FAQs loaded successfully"
    assert body["link"] == "/api/v1/support/contact"
    assert body["phone"]
    assert len(body["faqs"]) >= 6
    first = body["faqs"][0]
    assert first["id"]
    assert first["question"]
    assert first["answer"]
    assert any(
        item["question"] == "How do I join a training session?"
        for item in body["faqs"]
    )


def test_get_player_faqs_structure_question_answer(client: TestClient) -> None:
    response = client.get(FAQS_BASE)
    assert response.status_code == 200
    for item in response.json()["faqs"]:
        assert "question" in item
        assert "answer" in item
        assert item["question"]
        assert item["answer"]


def test_get_player_faqs_empty_state_200(client: TestClient) -> None:
    with patch("app.services.faq.get_player_faq_articles", return_value=[]):
        response = client.get(FAQS_BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "empty"
    assert body["faqs"] == []
    assert body["message"] == "No FAQs are available at this time"


def test_get_player_faq_by_id_200(client: TestClient) -> None:
    listed = client.get(FAQS_BASE)
    faq_id = listed.json()["faqs"][0]["id"]

    response = client.get(f"{FAQS_BASE}/{faq_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["id"] == faq_id
    assert body["question"]
    assert body["answer"]


def test_get_player_faq_by_id_404(client: TestClient) -> None:
    response = client.get(f"{FAQS_BASE}/{UUID('00000000-0000-4000-8000-000000000099')}")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FAQ_NOT_FOUND"


def test_faqs_contact_support_201(client: TestClient) -> None:
    response = client.post(FAQS_CONTACT_SUPPORT_BASE, json=SUPPORT_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Your support request has been submitted successfully"
    assert body["description"] == "We typically respond within 24 hours"
    assert body["id"]
    assert body["phone"] == "15558392001"
