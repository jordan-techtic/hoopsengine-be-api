"""Integration tests for coach edit profile API (HE-318)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import (
    ADMIN_EMAIL,
    PROFILE_BASE,
    REGULAR_EMAIL,
    VIEWER_EMAIL,
)

VALID_PROFILE_PAYLOAD = {
    "first_name": "Lebron",
    "last_name": "James",
    "phone_number": "+1 (555) 382-9102",
    "date_of_birth": "08/24/1992",
    "gender": "Male",
    "grade": "Academy Head",
    "username": "regularcoach",
    "email": REGULAR_EMAIL,
    "parent_guardian": "Not Applicable",
    "phone": "+1-555-0100",
}


def test_get_profile_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(PROFILE_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["title"] == "Edit Profile"
    assert body["first_name"] == "Regular"
    assert body["last_name"] == "Coach"
    assert body["email"] == REGULAR_EMAIL
    assert body["username"] == "regularcoach"
    assert "profile" in body
    assert body["profile"]["email"] == REGULAR_EMAIL


def test_update_profile_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.put(PROFILE_BASE, headers=coach_headers, json=VALID_PROFILE_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "saved"
    assert body["first_name"] == "Lebron"
    assert body["last_name"] == "James"
    assert body["phone_number"] == "+1 (555) 382-9102"
    assert body["date_of_birth"] == "08/24/1992"
    assert body["gender"] == "Male"
    assert body["grade"] == "Academy Head"
    assert body["parent_guardian"] == "Not Applicable"
    assert body["name"] == "Lebron James"


def test_update_profile_400_empty_first_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {**VALID_PROFILE_PAYLOAD, "first_name": "   "}
    response = client.put(PROFILE_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_profile_400_invalid_email(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {**VALID_PROFILE_PAYLOAD, "email": "not-an-email"}
    response = client.put(PROFILE_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_profile_400_invalid_phone(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {**VALID_PROFILE_PAYLOAD, "phone_number": "abc"}
    response = client.put(PROFILE_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "phone_number"


def test_update_profile_409_duplicate_email(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {**VALID_PROFILE_PAYLOAD, "email": ADMIN_EMAIL}
    response = client.put(PROFILE_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_IN_USE"


def test_update_profile_409_duplicate_username(
    client: TestClient,
    coach_headers: dict[str, str],
    viewer_headers: dict[str, str],
) -> None:
    viewer_payload = {
        "first_name": "Viewer",
        "last_name": "Player",
        "email": VIEWER_EMAIL,
        "username": "viewerplayer",
    }
    setup = client.put(PROFILE_BASE, headers=viewer_headers, json=viewer_payload)
    assert setup.status_code == 200

    payload = {**VALID_PROFILE_PAYLOAD, "username": "viewerplayer"}
    response = client.put(PROFILE_BASE, headers=coach_headers, json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USERNAME_ALREADY_IN_USE"


def test_update_profile_422_missing_required_fields(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.put(
        PROFILE_BASE,
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_profile_401_without_auth(client: TestClient) -> None:
    response = client.get(PROFILE_BASE)
    assert response.status_code == 401
