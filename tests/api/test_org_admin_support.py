"""Integration tests for organization admin Contact Support API (HE-413)."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import sync_engine

ORG_ADMIN_SUPPORT_CONTACT_BASE = "/api/v1/admin/support/contact"
CONFIRMATION_URL = f"{ORG_ADMIN_SUPPORT_CONTACT_BASE}/confirmation"

VALID_PAYLOAD = {
    "email": "orgadmin.support@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "Explain your problem or inquiry in detail here.",
}


@pytest.fixture(autouse=True)
def _clean_support_requests() -> None:
    with sync_engine.begin() as connection:
        connection.execute(text("DELETE FROM support_requests_staging"))


def test_post_org_admin_support_contact_201(client: TestClient) -> None:
    response = client.post(ORG_ADMIN_SUPPORT_CONTACT_BASE, json=VALID_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "submitted"
    assert body["message"] == "Your support request has been submitted successfully"
    assert body["description"] == "We typically respond within 24 hours"
    assert body["organization"] == "Hoops Engine"
    assert body["id"] == body["request_id"]
    assert body["email"] == "orgadmin.support@example.com"
    assert body["phone"] == "15558392001"
    assert body["phone_number"] == "15558392001"


def test_post_org_admin_support_contact_400_missing_email(client: TestClient) -> None:
    response = client.post(
        ORG_ADMIN_SUPPORT_CONTACT_BASE,
        json={**VALID_PAYLOAD, "email": ""},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_post_org_admin_support_contact_400_invalid_email(client: TestClient) -> None:
    response = client.post(
        ORG_ADMIN_SUPPORT_CONTACT_BASE,
        json={**VALID_PAYLOAD, "email": "not-an-email"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "email"


def test_post_org_admin_support_contact_400_message_too_long(client: TestClient) -> None:
    response = client.post(
        ORG_ADMIN_SUPPORT_CONTACT_BASE,
        json={**VALID_PAYLOAD, "message_description": "x" * 501},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "message_description"


def test_post_org_admin_support_contact_400_missing_required_fields(client: TestClient) -> None:
    response = client.post(
        ORG_ADMIN_SUPPORT_CONTACT_BASE,
        json={
            "email": "",
            "phone": "",
            "inquiry_subject": "",
            "message_description": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_org_admin_support_confirmation_200_with_request_id(client: TestClient) -> None:
    created = client.post(ORG_ADMIN_SUPPORT_CONTACT_BASE, json=VALID_PAYLOAD)
    assert created.status_code == 201
    request_id = created.json()["id"]

    response = client.get(CONFIRMATION_URL, params={"request_id": request_id})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "confirmed"
    assert body["message"] == "Your support request has been submitted successfully"
    assert body["organization"] == "Hoops Engine"
    assert body["id"] == request_id
    assert body["email"] == "orgadmin.support@example.com"
    assert body["inquiry_subject"] == "Technical Issue"
    assert body["message_description"] == VALID_PAYLOAD["message_description"]
    assert body["operating_hours"]
    assert body["live_chat_label"]


def test_get_org_admin_support_confirmation_200_default(client: TestClient) -> None:
    response = client.get(CONFIRMATION_URL)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Your support request has been submitted successfully"
    assert body["organization"] == "Hoops Engine"
    assert body["email"]
    assert body["phone"]


def test_get_org_admin_support_confirmation_404_missing_request(client: TestClient) -> None:
    missing_id = UUID("00000000-0000-4000-8000-000000999999")
    response = client.get(CONFIRMATION_URL, params={"request_id": str(missing_id)})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SUPPORT_REQUEST_NOT_FOUND"
