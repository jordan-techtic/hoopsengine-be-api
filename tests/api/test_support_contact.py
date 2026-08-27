"""Integration tests for public Contact Support API (HE-320)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import sync_engine

SUPPORT_CONTACT_BASE = "/api/v1/support/contact"

VALID_PAYLOAD = {
    "email": "contact.user@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "Explain your problem or inquiry in detail here.",
}


@pytest.fixture(autouse=True)
def _clean_support_requests() -> None:
    with sync_engine.begin() as connection:
        connection.execute(text("DELETE FROM support_requests_staging"))


def test_post_valid_201(client: TestClient) -> None:
    response = client.post(SUPPORT_CONTACT_BASE, json=VALID_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "submitted"
    assert body["description"] == "We typically respond within 24 hours"
    assert body["message"] == "Your support request has been submitted successfully"
    assert body["id"] == body["request_id"]
    assert body["email"] == "contact.user@example.com"
    assert body["phone"] == "15558392001"


def test_missing_required_fields_400(client: TestClient) -> None:
    response = client.post(
        SUPPORT_CONTACT_BASE,
        json={
            "email": "",
            "phone": "",
            "inquiry_subject": "",
            "message_description": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_email_400(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "email": "not-an-email"}
    response = client.post(SUPPORT_CONTACT_BASE, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_non_numeric_phone_400(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "phone": "abc-def-ghij"}
    response = client.post(SUPPORT_CONTACT_BASE, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_invalid_inquiry_subject_409(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "inquiry_subject": "Random Topic"}
    response = client.post(SUPPORT_CONTACT_BASE, json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_INQUIRY_SUBJECT"


def test_message_exceeds_500_400(client: TestClient) -> None:
    payload = {**VALID_PAYLOAD, "message_description": "x" * 501}
    response = client.post(SUPPORT_CONTACT_BASE, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_duplicate_submission_409(client: TestClient) -> None:
    first = client.post(SUPPORT_CONTACT_BASE, json=VALID_PAYLOAD)
    assert first.status_code == 201

    duplicate = client.post(SUPPORT_CONTACT_BASE, json=VALID_PAYLOAD)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_SUPPORT_SUBMISSION"


def test_get_contact_info_200(client: TestClient) -> None:
    response = client.get(f"{SUPPORT_CONTACT_BASE}/info")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert body["email"]
    assert body["phone"]
    assert body["description"]
