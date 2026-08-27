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

import pytest


@pytest.mark.parametrize("missing_field", [
    "first_name",
    "last_name",
    "username",
    "email",
    "password",
    "confirm_password",
    "terms_accepted",
])
def test_register_missing_required_field_returns_validation_error(
    client: TestClient,
    seeded_users: dict,
    missing_field: str,
) -> None:
    """HE-323: missing required fields return a validation error (422 via Pydantic)."""
    payload = _register_payload()
    del payload[missing_field]
    response = client.post(REGISTER_BASE, json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_register_success_response_contains_all_frontend_fields(
    client: TestClient,
    seeded_users: dict,
) -> None:
    """HE-323: successful registration returns complete response body for FE Register."""
    response = client.post(
        REGISTER_BASE,
        json=_register_payload(
            username="fecontract",
            email="fe.contract@example.com",
        ),
    )
    assert response.status_code == 201
    body = response.json()
    for key in (
        "first_name",
        "last_name",
        "username",
        "email",
        "access_token",
        "expires_in_hours",
        "link",
        "description",
        "message",
        "status",
    ):
        assert key in body
    assert body["phone"] is None or isinstance(body.get("phone"), str)


def test_register_unicode_name_success_201(client: TestClient, seeded_users: dict) -> None:
    """Edge case: unicode characters in name fields are accepted."""
    response = client.post(
        REGISTER_BASE,
        json=_register_payload(
            first_name="José",
            last_name="Müller",
            username="unicode_coach",
            email="unicode.coach@example.com",
        ),
    )
    assert response.status_code == 201
    assert response.json()["name"] == "José Müller"


def test_register_username_max_length_boundary_400(client: TestClient, seeded_users: dict) -> None:
    """Edge case: username longer than 30 characters is rejected."""
    response = client.post(
        REGISTER_BASE,
        json=_register_payload(username="a" * 31, email="long.user@example.com"),
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "username"
