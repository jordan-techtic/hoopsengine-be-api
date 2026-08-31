"""Integration tests for player Contact Support API (HE-225)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import (
    PLAYER_SUPPORT_CONTACT_BASE,
    PLAYER_SUPPORT_INQUIRIES_BASE,
    sync_engine,
)

VALID_PAYLOAD = {
    "email": "player.support@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "Explain your problem or inquiry in detail here.",
}


@pytest.fixture(autouse=True)
def _clean_support_requests() -> None:
    with sync_engine.begin() as connection:
        connection.execute(text("DELETE FROM support_requests_staging"))


def test_post_support_inquiry_valid_201(client: TestClient) -> None:
    response = client.post(PLAYER_SUPPORT_INQUIRIES_BASE, json=VALID_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "submitted"
    assert body["description"] == "We typically respond within 24 hours"
    assert body["message"] == "Your support request has been submitted successfully"
    assert body["email"] == "player.support@example.com"
    assert body["phone"] == "15558392001"
    assert body["id"]


def test_post_support_inquiry_empty_email_400(client: TestClient) -> None:
    response = client.post(
        PLAYER_SUPPORT_INQUIRIES_BASE,
        json={**VALID_PAYLOAD, "email": ""},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_post_support_inquiry_invalid_email_400(client: TestClient) -> None:
    response = client.post(
        PLAYER_SUPPORT_INQUIRIES_BASE,
        json={**VALID_PAYLOAD, "email": "not-an-email"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_post_support_inquiry_message_too_long_400(client: TestClient) -> None:
    response = client.post(
        PLAYER_SUPPORT_INQUIRIES_BASE,
        json={**VALID_PAYLOAD, "message_description": "x" * 501},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "message_description"


def test_get_support_contact_200(client: TestClient) -> None:
    response = client.get(PLAYER_SUPPORT_CONTACT_BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["email"]
    assert body["phone"]
    assert body["description"]
    assert body["operating_hours"] == "Mon-Fri, 9am - 6pm EST"
    assert body["live_chat_label"] == "Start instant chat"
