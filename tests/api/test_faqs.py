"""Integration tests for public FAQs API (HE-271 / BE FAQs)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import sync_engine

FAQS_BASE = "/api/v1/faqs"
SUPPORT_CONTACT_BASE = "/api/v1/support/contact"

SUPPORT_PAYLOAD = {
    "email": "faq.user@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "Need help from the FAQs screen.",
}


@pytest.fixture(autouse=True)
def _clean_support_requests() -> None:
    with sync_engine.begin() as connection:
        connection.execute(text("DELETE FROM support_requests_staging"))


def test_get_faqs_200(client: TestClient) -> None:
    response = client.get(FAQS_BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["title"] == "How can we help you?"
    assert body["description"]
    assert body["message"] == "FAQs loaded successfully"
    assert body["link"] == "/api/v1/support/contact"
    assert body["phone"]
    assert len(body["faqs"]) >= 2
    first = body["faqs"][0]
    assert first["id"]
    assert first["question"]
    assert first["answer"]
    assert any(
        item["question"] == "How do I create a new drill?"
        for item in body["faqs"]
    )


def test_get_faqs_empty_state_200(client: TestClient) -> None:
    with patch("app.services.faq.get_help_articles", return_value=[]):
        response = client.get(FAQS_BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "empty"
    assert body["faqs"] == []
    assert body["message"] == "No FAQs are available at this time"
    assert body["phone"]


def test_get_faqs_invalid_phone_query_400(client: TestClient) -> None:
    response = client.get(FAQS_BASE, params={"phone": "not-a-phone"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_support_contact_from_faqs_flow_201(client: TestClient) -> None:
    response = client.post(SUPPORT_CONTACT_BASE, json=SUPPORT_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Your support request has been submitted successfully"
    assert body["description"] == "We typically respond within 24 hours"


def test_support_contact_invalid_parameters_400(client: TestClient) -> None:
    response = client.post(
        SUPPORT_CONTACT_BASE,
        json={
            "email": "bad-email",
            "phone": "abc",
            "inquiry_subject": "",
            "message_description": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
