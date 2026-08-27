"""Integration tests for POST /api/v1/register (HE-323)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import (
    REGISTER_BASE,
    REGULAR_EMAIL,
    TEST_MISMATCH_PASSWORD,
    TEST_VALID_PASSWORD,
    TEST_WEAK_PASSWORD_LONG,
)


def _register_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "John",
        "last_name": "Doe",
        "username": "newcoach",
        "email": "new.coach@example.com",
        "password": TEST_VALID_PASSWORD,
        "confirm_password": TEST_VALID_PASSWORD,
        "terms_accepted": True,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_register_success_201_creates_coach(
    client: TestClient,
    seeded_users: dict,
) -> None:
    """Valid registration returns 201 and creates a coach record."""
    response = client.post(REGISTER_BASE, json=_register_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"]
    assert body["status"] == "pending_verification"
    assert body["error"] is None
    assert body["username"] == "newcoach"
    assert body["email"] == "new.coach@example.com"
    assert body["first_name"] == "John"
    assert body["last_name"] == "Doe"
    assert body["name"] == "John Doe"
    assert "id" in body
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert "password" not in body
    assert "encrypted_password" not in body


def test_register_empty_first_name_400(client: TestClient, seeded_users: dict) -> None:
    response = client.post(REGISTER_BASE, json=_register_payload(first_name="   "))
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "first_name"


def test_register_duplicate_email_409(client: TestClient, seeded_users: dict) -> None:
    response = client.post(
        REGISTER_BASE,
        json=_register_payload(email=REGULAR_EMAIL, username="uniquecoach"),
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "EMAIL_ALREADY_IN_USE"
    assert body["error"]["details"][0]["field"] == "email"


def test_register_duplicate_username_409(client: TestClient, seeded_users: dict) -> None:
    first = client.post(
        REGISTER_BASE,
        json=_register_payload(email="first@example.com", username="takenname"),
    )
    assert first.status_code == 201
    second = client.post(
        REGISTER_BASE,
        json=_register_payload(email="second@example.com", username="takenname"),
    )
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "USERNAME_ALREADY_IN_USE"
    assert body["error"]["details"][0]["field"] == "username"


def test_register_weak_password_400(client: TestClient, seeded_users: dict) -> None:
    response = client.post(
        REGISTER_BASE,
        json=_register_payload(
            password=TEST_WEAK_PASSWORD_LONG,
            confirm_password=TEST_WEAK_PASSWORD_LONG,
        ),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "password"


def test_register_terms_not_accepted_400(client: TestClient, seeded_users: dict) -> None:
    response = client.post(REGISTER_BASE, json=_register_payload(terms_accepted=False))
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "terms_accepted"


def test_register_missing_required_field_422(client: TestClient, seeded_users: dict) -> None:
    payload = _register_payload()
    del payload["username"]
    response = client.post(REGISTER_BASE, json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_register_password_mismatch_400(client: TestClient, seeded_users: dict) -> None:
    response = client.post(
        REGISTER_BASE,
        json=_register_payload(confirm_password=TEST_MISMATCH_PASSWORD),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "confirm_password"


def test_register_invalid_email_422(client: TestClient, seeded_users: dict) -> None:
    response = client.post(REGISTER_BASE, json=_register_payload(email="not-an-email"))
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
