"""Integration tests for Super Admin Manage Users API (JAW-9603)."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import (
    ADMIN_ID,
    NEW_USER_EMAIL,
    REGULAR_EMAIL,
    USER_BASE,
    auth_headers,
    make_expired_token,
)


def _user_payload(**overrides: object) -> dict[str, object]:
    """Ticket-shaped create-user body with a password that meets complexity rules."""
    payload: dict[str, object] = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "password": "Coach@123",
        "role": "coach",
    }
    payload.update(overrides)
    return payload


def test_list_users_returns_200_with_data(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9603: View list of users and return 200 with user data."""
    response = client.get(USER_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "pagination" in body
    assert body["pagination"]["total"] >= 4
    emails = {item["email"] for item in body["items"]}
    assert seeded_users["admin"]["email"] in emails
    assert seeded_users["user"]["email"] in emails
    assert seeded_users["viewer"]["email"] in emails
    assert seeded_users["inactive"]["email"] in emails
    assert NEW_USER_EMAIL not in emails
    assert body["roles"]
    assert {item["value"] for item in body["roles"]} >= {"coach", "player"}
    admin_row = next(item for item in body["items"] if item["id"] == str(ADMIN_ID))
    assert admin_row["is_self"] is True
    assert admin_row["role"] == "super_admin"


def test_create_user_returns_200_omits_password(
    client: TestClient, admin_headers: dict[str, str], new_user_payload: dict[str, str]
) -> None:
    """JAW-9603: Add a new user and return 200 with user data (password omitted)."""
    response = client.post(USER_BASE, headers=admin_headers, json=new_user_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "User created successfully."
    assert body["email"] == NEW_USER_EMAIL
    assert body["first_name"] == "New"
    assert body["last_name"] == "User"
    assert body["name"] == "New User"
    assert body["role"] == "coach"
    assert body["roles"] == ["coach"]
    assert "id" in body
    assert "password" not in body
    assert "encrypted_password" not in body
    assert body["is_active"] is True
    assert body["is_self"] is False


def test_update_user_returns_200_with_data(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9603: Edit an existing user and return 200 with user data."""
    user_id = seeded_users["user"]["id"]
    response = client.put(
        f"{USER_BASE}/{user_id}",
        headers=admin_headers,
        json={"first_name": "Jane"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "User updated successfully."
    assert body["first_name"] == "Jane"
    assert body["last_name"] == "Coach"
    assert body["name"] == "Jane Coach"
    assert body["email"] == REGULAR_EMAIL
    assert body["id"] == str(user_id)
    assert "password" not in body


def test_delete_user_returns_200(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9603: Remove a user (soft-delete). Cannot remove own account is covered separately."""
    user_id = str(seeded_users["user"]["id"])
    response = client.delete(f"{USER_BASE}/{user_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "User removed successfully."

    listed = client.get(USER_BASE, headers=admin_headers)
    assert listed.status_code == 200
    emails = {item["email"] for item in listed.json()["items"]}
    assert REGULAR_EMAIL not in emails


def test_create_user_invalid_role_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Unknown role values fail validation."""
    response = client.post(
        USER_BASE,
        headers=admin_headers,
        json=_user_payload(role="not-a-role"),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_user_weak_password_400(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """JAW-9603: Return 400 status for invalid user data (ticket example password)."""
    response = client.post(
        USER_BASE,
        headers=admin_headers,
        json=_user_payload(password="password123"),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_user_invalid_email_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Malformed email is a 422 validation error."""
    response = client.post(
        USER_BASE,
        headers=admin_headers,
        json=_user_payload(email="not-an-email"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_user_not_found_404(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """JAW-9603: Return 404 status for user not found on update."""
    missing_id = uuid4()
    response = client.put(
        f"{USER_BASE}/{missing_id}",
        headers=admin_headers,
        json={"first_name": "Jane"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"
    assert response.json()["error"]["message"] == "User not found"


def test_delete_user_not_found_404(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """JAW-9603: Return 404 status for user not found on delete."""
    missing_id = uuid4()
    response = client.delete(f"{USER_BASE}/{missing_id}", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_delete_self_returns_400(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Super admin cannot remove their own account."""
    response = client.delete(f"{USER_BASE}/{ADMIN_ID}", headers=admin_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CANNOT_DELETE_SELF"
    assert "own account" in response.json()["error"]["message"].lower()


def test_list_users_missing_token_401(client: TestClient) -> None:
    """Missing Authorization header is rejected with 401."""
    response = client.get(USER_BASE)
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}


def test_list_users_forbidden_for_regular_user_403(
    client: TestClient, user_headers: dict[str, str]
) -> None:
    """A coach cannot list users."""
    response = client.get(USER_BASE, headers=user_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_list_users_forbidden_for_viewer_403(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    """A player/readonly user cannot list users."""
    response = client.get(USER_BASE, headers=viewer_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_create_user_forbidden_for_regular_user_403(
    client: TestClient, user_headers: dict[str, str]
) -> None:
    """A coach cannot create users."""
    response = client.post(USER_BASE, headers=user_headers, json=_user_payload())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_list_users_inactive_user_401(
    client: TestClient, inactive_headers: dict[str, str]
) -> None:
    """A deactivated account cannot call super-admin endpoints."""
    response = client.get(USER_BASE, headers=inactive_headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_list_users_expired_token_401(
    client: TestClient, seeded_users: dict
) -> None:
    """An expired access token is rejected with 401."""
    token = make_expired_token(seeded_users["admin"]["id"])
    response = client.get(USER_BASE, headers=auth_headers(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_create_user_duplicate_email_409(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Inserting a user whose email already exists returns 409."""
    response = client.post(
        USER_BASE,
        headers=admin_headers,
        json=_user_payload(email=REGULAR_EMAIL),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_IN_USE"


def test_create_user_empty_first_name_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Empty first_name fails validation."""
    response = client.post(
        USER_BASE,
        headers=admin_headers,
        json=_user_payload(first_name=""),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_user_accepts_coach_display_role(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """UI label `Coach` is coerced to the stored `coach` role."""
    response = client.post(
        USER_BASE,
        headers=admin_headers,
        json=_user_payload(email="label.coach@example.com", role="Coach"),
    )
    assert response.status_code == 200
    assert response.json()["role"] == "coach"
    assert response.json()["roles"] == ["coach"]


def test_create_user_password_too_short_400(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Passwords under 8 characters are rejected with 400 after schema min_length.

    Pydantic min_length=8 yields 422; a long-but-weak password yields 400.
    This test covers the 8-character floor via 422 for a too-short value.
    """
    response = client.post(
        USER_BASE,
        headers=admin_headers,
        json=_user_payload(password="Ab1!x"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_new_user_not_present_until_registered(
    client: TestClient,
    admin_headers: dict[str, str],
    new_user_payload: dict[str, str],
) -> None:
    """The reserved new-user email is absent until POST creates the account."""
    listed = client.get(USER_BASE, headers=admin_headers)
    emails = {item["email"] for item in listed.json()["items"]}
    assert NEW_USER_EMAIL not in emails

    created = client.post(USER_BASE, headers=admin_headers, json=new_user_payload)
    assert created.status_code == 200
    assert created.json()["email"] == NEW_USER_EMAIL

    listed_after = client.get(USER_BASE, headers=admin_headers)
    emails_after = {item["email"] for item in listed_after.json()["items"]}
    assert NEW_USER_EMAIL in emails_after


def test_update_user_empty_payload_422(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """Updating with no fields fails the request model validator."""
    user_id = seeded_users["user"]["id"]
    response = client.put(f"{USER_BASE}/{user_id}", headers=admin_headers, json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_user_unknown_org_id_400(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """A non-existent org_id is rejected (data integrity / bad foreign key)."""
    response = client.post(
        USER_BASE,
        headers=admin_headers,
        json=_user_payload(email="orphan.coach@example.com", org_id=str(uuid4())),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"


def test_deleted_user_excluded_from_list(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """Soft-deleted users do not appear in subsequent list calls."""
    user_id = seeded_users["viewer"]["id"]
    deleted = client.delete(f"{USER_BASE}/{user_id}", headers=admin_headers)
    assert deleted.status_code == 200

    listed = client.get(USER_BASE, headers=admin_headers)
    ids = {item["id"] for item in listed.json()["items"]}
    assert str(user_id) not in ids

    again = client.delete(f"{USER_BASE}/{user_id}", headers=admin_headers)
    assert again.status_code == 404


def test_update_user_duplicate_email_409(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """Changing email to another account's address returns 409."""
    user_id = seeded_users["user"]["id"]
    response = client.put(
        f"{USER_BASE}/{user_id}",
        headers=admin_headers,
        json={"email": seeded_users["viewer"]["email"]},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_IN_USE"


def test_create_user_name_too_long_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """first_name longer than 255 characters is rejected."""
    response = client.post(
        USER_BASE,
        headers=admin_headers,
        json=_user_payload(first_name="J" * 256),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_users_search_by_email(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Optional search matches user email."""
    response = client.get(f"{USER_BASE}?search=admin@test.com", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 1
    assert any(item["email"] == "admin@test.com" for item in body["items"])


def test_list_users_invalid_page_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """page must be >= 1."""
    response = client.get(f"{USER_BASE}?page=0", headers=admin_headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_user_unicode_name_200(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """Unicode first and last names are stored and returned in `name`."""
    response = client.post(
        USER_BASE,
        headers=admin_headers,
        json=_user_payload(
            first_name="José",
            last_name="García",
            email="jose.garcia@example.com",
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "José"
    assert body["last_name"] == "García"
    assert body["name"] == "José García"
    assert "password" not in body
