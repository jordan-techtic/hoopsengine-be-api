"""Integration tests for player edit profile API (HE-223)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import (
    ADMIN_EMAIL,
    PLAYER_PROFILE_BASE,
    VIEWER_EMAIL,
)

VALID_PROFILE_PAYLOAD = {
    "first_name": "Lebron",
    "last_name": "James",
    "phone_number": "+1 (555) 382-9102",
    "date_of_birth": "08/24/1992",
    "gender": "Male",
    "grade": "Academy Head",
    "username": "viewerplayer",
    "email": VIEWER_EMAIL,
    "parent_guardian": "Not Applicable",
    "phone": "+1-555-0100",
}


def test_get_player_profile_200(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.get(PLAYER_PROFILE_BASE, headers=viewer_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["title"] == "Edit Profile"
    assert body["first_name"] == "Viewer"
    assert body["last_name"] == "Player"
    assert body["email"] == VIEWER_EMAIL
    assert body["username"] == "viewerplayer"
    assert body["name"] == "Viewer Player"
    assert "profile" in body
    assert body["profile"]["email"] == VIEWER_EMAIL


def test_update_player_profile_200(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.put(
        PLAYER_PROFILE_BASE,
        headers=viewer_headers,
        json=VALID_PROFILE_PAYLOAD,
    )
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
    assert body["message"] == "Profile updated successfully"


def test_update_player_profile_400_empty_first_name(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    payload = {**VALID_PROFILE_PAYLOAD, "first_name": "   "}
    response = client.put(PLAYER_PROFILE_BASE, headers=viewer_headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "first_name"


def test_update_player_profile_400_empty_last_name(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    payload = {**VALID_PROFILE_PAYLOAD, "last_name": "   "}
    response = client.put(PLAYER_PROFILE_BASE, headers=viewer_headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "last_name"


def test_update_player_profile_400_invalid_email(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    payload = {**VALID_PROFILE_PAYLOAD, "email": "not-an-email"}
    response = client.put(PLAYER_PROFILE_BASE, headers=viewer_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_player_profile_400_invalid_phone(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    payload = {**VALID_PROFILE_PAYLOAD, "phone_number": "abc"}
    response = client.put(PLAYER_PROFILE_BASE, headers=viewer_headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "phone_number"


def test_update_player_profile_409_duplicate_email(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    payload = {**VALID_PROFILE_PAYLOAD, "email": ADMIN_EMAIL}
    response = client.put(PLAYER_PROFILE_BASE, headers=viewer_headers, json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_IN_USE"


def test_update_player_profile_409_duplicate_username(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    payload = {**VALID_PROFILE_PAYLOAD, "username": "regularcoach"}
    response = client.put(PLAYER_PROFILE_BASE, headers=viewer_headers, json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USERNAME_ALREADY_IN_USE"


def test_update_player_profile_422_missing_required_fields(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.put(
        PLAYER_PROFILE_BASE,
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_player_profile_401_without_auth(client: TestClient) -> None:
    response = client.get(PLAYER_PROFILE_BASE)
    assert response.status_code == 401


def test_player_profile_403_for_coach(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(PLAYER_PROFILE_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
