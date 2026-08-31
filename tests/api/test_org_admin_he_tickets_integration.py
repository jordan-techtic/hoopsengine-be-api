"""Consolidated integration tests for org-admin HE tickets (HE-410 through HE-362).

Maps every ticket acceptance criterion to at least one runnable pytest case.
Reuses PostgreSQL fixtures from tests/conftest.py and shared seed helpers from
tests/fixtures/org_admin_he_tickets.py. External email (SendGrid) is mocked.

Run: pytest tests/api/test_org_admin_he_tickets_integration.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import (
    ORG_ADMIN_CHANGE_PASSWORD_BASE,
    ORG_ADMIN_COACHES_BASE,
    ORG_ADMIN_EDIT_PLAYERS_BASE,
    ORG_ADMIN_INVITE_COACH_BASE,
    ORG_ADMIN_SEARCH_COACHES_BASE,
    ORG_ADMIN_TEAMS_BASE,
    REGULAR_EMAIL,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_BOB_ID,
    TEAMS_BASE,
    TEST_INVALID_PASSWORD,
    TEST_NEW_SECURE_PASSWORD,
    TEST_VALID_PASSWORD,
    TEST_WEAK_PASSWORD,
    auth_headers,
    create_access_token,
    sync_engine,
)
from tests.fixtures.org_admin_he_tickets import (
    HE_COACH_ID,
    HE_COACH_USER_ID,
    HE_ORG_ADMIN_ID,
    HE_PLAYER_ID,
    HE_TEAM_ID,
    MISSING_COACH_ID,
    MISSING_PLAYER_ID,
    MISSING_TEAM_ID,
    seed_he_ticket_coach,
    seed_he_ticket_org_admin_headers,
    seed_he_ticket_player,
    seed_he_ticket_team,
)

VALID_CHANGE_PASSWORD = {
    "current_password": TEST_VALID_PASSWORD,
    "new_password": TEST_NEW_SECURE_PASSWORD,
    "confirm_password": TEST_NEW_SECURE_PASSWORD,
    "phone": "+1-555-0100",
    "password": TEST_NEW_SECURE_PASSWORD,
}

VALID_PLAYER_UPDATE = {
    "full_name": "Sarah Jenkins",
    "email": "sarah.jenkins@school.edu",
    "phone": "+1 (555) 123-4567",
    "team_assignment": "Varsity Squad",
}

VALID_COACH_UPDATE = {
    "full_name": "Sarah Jenkins",
    "email": "sarah.jenkins@school.edu",
    "phone": "+1 (555) 123-4567",
    "team_assignment": "Varsity Squad",
}

VALID_TEAM_CREATE = {
    "name": "Varsity Boys",
    "email": "newcoach@school.edu",
    "season": "2025-2026",
    "age_group": "16-18",
    "phone": "+1-555-0100",
    "coaches": ["Coach Taylor"],
    "players": ["Sarah Jenkins"],
}

VALID_LISTING_CREATE = {
    "name": "Listing Squad",
    "age_group": "U16",
    "coaches": [{"name": "John Doe"}],
    "players": [{"name": "Player One"}, {"name": "Player Two"}],
    "phone": "+1-555-0100",
}


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    return seed_he_ticket_org_admin_headers()


@pytest.fixture(autouse=True)
def _seed_domain(seed_he_ticket_player, seed_he_ticket_coach, seed_he_ticket_team) -> None:
    """Ensure client-domain rows exist for player/coach/team tests."""


@pytest.fixture
def mock_invite_email():
    with patch("app.services.org_admin_invite_coach.send_coach_invite_email") as mocked:
        mocked.return_value = None
        yield mocked


def _restore_org_admin_password() -> None:
    with Session(sync_engine) as session:
        user = session.get(User, HE_ORG_ADMIN_ID)
        if user is not None:
            user.encrypted_password = hash_password(TEST_VALID_PASSWORD)
            session.commit()


# --- HE-410 Change Password ---


def test_he410_change_password_success_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    try:
        response = client.post(ORG_ADMIN_CHANGE_PASSWORD_BASE, headers=org_admin_headers, json=VALID_CHANGE_PASSWORD)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["message"] == "Password changed successfully"
        assert body["id"] == str(HE_ORG_ADMIN_ID)
    finally:
        _restore_org_admin_password()


def test_he410_wrong_current_password_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_CHANGE_PASSWORD)
    payload["current_password"] = TEST_INVALID_PASSWORD
    response = client.post(ORG_ADMIN_CHANGE_PASSWORD_BASE, headers=org_admin_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "current_password"


def test_he410_weak_password_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_CHANGE_PASSWORD)
    payload["new_password"] = TEST_WEAK_PASSWORD
    payload["confirm_password"] = TEST_WEAK_PASSWORD
    response = client.post(ORG_ADMIN_CHANGE_PASSWORD_BASE, headers=org_admin_headers, json=payload)
    assert response.status_code == 400


def test_he410_password_mismatch_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_CHANGE_PASSWORD)
    payload["confirm_password"] = "MismatchPass999!"
    response = client.post(ORG_ADMIN_CHANGE_PASSWORD_BASE, headers=org_admin_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "confirm_password"


def test_he410_change_password_missing_token_401(client: TestClient) -> None:
    response = client.post(ORG_ADMIN_CHANGE_PASSWORD_BASE, json=VALID_CHANGE_PASSWORD)
    assert response.status_code == 401


# --- HE-378 Edit Player ---


def test_he378_get_player_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{HE_PLAYER_ID}", headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == str(HE_PLAYER_ID)
    assert body["full_name"]


def test_he378_update_player_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.put(
        f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{HE_PLAYER_ID}",
        headers=org_admin_headers,
        json=VALID_PLAYER_UPDATE,
    )
    assert response.status_code == 200
    assert response.json()["email"] == VALID_PLAYER_UPDATE["email"]


def test_he378_duplicate_email_409(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_PLAYER_UPDATE)
    payload["email"] = "bob.smith@varsityacademy.com"
    response = client.put(
        f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{HE_PLAYER_ID}",
        headers=org_admin_headers,
        json=payload,
    )
    assert response.status_code == 409


def test_he378_empty_full_name_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_PLAYER_UPDATE)
    payload["full_name"] = ""
    response = client.put(
        f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{HE_PLAYER_ID}",
        headers=org_admin_headers,
        json=payload,
    )
    assert response.status_code == 400


def test_he378_empty_email_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_PLAYER_UPDATE)
    payload["email"] = ""
    response = client.put(
        f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{HE_PLAYER_ID}",
        headers=org_admin_headers,
        json=payload,
    )
    assert response.status_code == 400


def test_he378_player_not_found_404(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{MISSING_PLAYER_ID}", headers=org_admin_headers)
    assert response.status_code == 404


def test_he378_invalid_email_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_PLAYER_UPDATE)
    payload["email"] = "not-an-email"
    response = client.put(
        f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{HE_PLAYER_ID}",
        headers=org_admin_headers,
        json=payload,
    )
    assert response.status_code == 400


def test_he378_edit_player_forbidden_403(client: TestClient, seeded_users: dict) -> None:
    headers = auth_headers(create_access_token(REGULAR_USER_ID))
    response = client.get(f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{HE_PLAYER_ID}", headers=headers)
    assert response.status_code == 403


# --- HE-375 Edit Coach ---


def test_he375_get_coach_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(f"{ORG_ADMIN_COACHES_BASE}/{HE_COACH_ID}", headers=org_admin_headers)
    assert response.status_code == 200
    assert response.json()["coach_id"] == str(HE_COACH_ID)


def test_he375_update_coach_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{HE_COACH_ID}",
        headers=org_admin_headers,
        json=VALID_COACH_UPDATE,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == VALID_COACH_UPDATE["email"]
    assert body["full_name"] == VALID_COACH_UPDATE["full_name"]


def test_he375_invalid_email_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_COACH_UPDATE)
    payload["email"] = "bad-email"
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{HE_COACH_ID}",
        headers=org_admin_headers,
        json=payload,
    )
    assert response.status_code == 400


def test_he375_duplicate_email_409(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_COACH_UPDATE)
    payload["email"] = REGULAR_EMAIL
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{HE_COACH_ID}",
        headers=org_admin_headers,
        json=payload,
    )
    assert response.status_code == 409


def test_he375_empty_phone_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_COACH_UPDATE)
    payload["phone"] = ""
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{HE_COACH_ID}",
        headers=org_admin_headers,
        json=payload,
    )
    assert response.status_code == 400


def test_he375_coach_forbidden_403(client: TestClient, seeded_users: dict) -> None:
    headers = auth_headers(create_access_token(REGULAR_USER_ID))
    response = client.put(
        f"{ORG_ADMIN_COACHES_BASE}/{HE_COACH_ID}",
        headers=headers,
        json=VALID_COACH_UPDATE,
    )
    assert response.status_code == 403


# --- HE-372 Edit Team (admin teams) ---


def test_he372_get_team_for_edit_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(f"{ORG_ADMIN_TEAMS_BASE}/{HE_TEAM_ID}", headers=org_admin_headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(HE_TEAM_ID)


def test_he372_update_team_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.put(
        f"{ORG_ADMIN_TEAMS_BASE}/{HE_TEAM_ID}",
        headers=org_admin_headers,
        json={"team_name": "Updated Varsity", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200


def test_he372_empty_team_name_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.put(
        f"{ORG_ADMIN_TEAMS_BASE}/{HE_TEAM_ID}",
        headers=org_admin_headers,
        json={"team_name": ""},
    )
    assert response.status_code == 400


def test_he372_duplicate_team_name_409(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json={"team_name": "Duplicate Squad", "team_code": "DUP-001", "age_group": "U16", "coaches": []},
    )
    duplicate = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=org_admin_headers,
        json={"team_name": "Duplicate Squad", "team_code": "DUP-002", "age_group": "U16", "coaches": []},
    )
    assert duplicate.status_code == 409


def test_he372_update_team_forbidden_403(client: TestClient, seeded_users: dict) -> None:
    headers = auth_headers(create_access_token(REGULAR_USER_ID))
    response = client.put(
        f"{ORG_ADMIN_TEAMS_BASE}/{HE_TEAM_ID}",
        headers=headers,
        json={"team_name": "Forbidden"},
    )
    assert response.status_code == 403


# --- HE-363 Invite Coach ---


def test_he363_invite_coach_201(client: TestClient, org_admin_headers: dict[str, str], mock_invite_email) -> None:
    response = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=org_admin_headers,
        json={"email": "invite.he363@academy.org", "phone": "+1-555-0100", "company": "Acme"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "invite.he363@academy.org"
    mock_invite_email.assert_called_once()


def test_he363_invalid_email_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=org_admin_headers,
        json={"email": "not-valid"},
    )
    assert response.status_code == 400


def test_he363_empty_email_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=org_admin_headers,
        json={"email": ""},
    )
    assert response.status_code == 400


def test_he363_duplicate_email_409(client: TestClient, org_admin_headers: dict[str, str], mock_invite_email) -> None:
    email = "duplicate.he363@academy.org"
    first = client.post(ORG_ADMIN_INVITE_COACH_BASE, headers=org_admin_headers, json={"email": email})
    assert first.status_code == 201
    second = client.post(ORG_ADMIN_INVITE_COACH_BASE, headers=org_admin_headers, json={"email": email})
    assert second.status_code == 409


def test_he363_search_coaches_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(
        ORG_ADMIN_SEARCH_COACHES_BASE,
        headers=org_admin_headers,
        params={"query": "Jane"},
    )
    assert response.status_code == 200
    assert isinstance(response.json()["items"], list)


def test_he363_invite_forbidden_403(client: TestClient, seeded_users: dict) -> None:
    headers = auth_headers(create_access_token(REGULAR_USER_ID))
    response = client.post(
        ORG_ADMIN_INVITE_COACH_BASE,
        headers=headers,
        json={"email": "forbidden@academy.org"},
    )
    assert response.status_code == 403


# --- HE-369 Remove Coach ---


def test_he369_get_coach_for_removal_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(f"{ORG_ADMIN_COACHES_BASE}/{HE_COACH_ID}", headers=org_admin_headers)
    assert response.status_code == 200
    assert response.json()["confirmation_message"]


def test_he369_remove_coach_204(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    removable_id = UUID("00000000-0000-4000-8000-0000000000c1")
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO coaches (id, org_id, first_name, last_name, email)
                VALUES (:id, :org_id, 'Removable', 'Coach', 'removable@academy.org')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": removable_id, "org_id": SEEDED_ORG_ID},
        )
    response = client.delete(f"{ORG_ADMIN_COACHES_BASE}/{removable_id}", headers=org_admin_headers)
    assert response.status_code == 204


def test_he369_remove_coach_404(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.delete(f"{ORG_ADMIN_COACHES_BASE}/{MISSING_COACH_ID}", headers=org_admin_headers)
    assert response.status_code == 404


def test_he369_remove_coach_forbidden_403(client: TestClient, seeded_users: dict) -> None:
    headers = auth_headers(create_access_token(REGULAR_USER_ID))
    response = client.delete(f"{ORG_ADMIN_COACHES_BASE}/{HE_COACH_ID}", headers=headers)
    assert response.status_code == 403


def test_he369_remove_invalid_phone_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.delete(
        f"{ORG_ADMIN_COACHES_BASE}/{HE_COACH_ID}",
        headers=org_admin_headers,
        json={"phone": "not-a-phone"},
    )
    assert response.status_code == 400


# --- HE-365 Team Details (/api/v1/teams) ---


def test_he365_get_team_details_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    create = client.post(TEAMS_BASE, headers=org_admin_headers, json=VALID_TEAM_CREATE)
    assert create.status_code == 201
    team_id = create.json()["id"]
    response = client.get(f"{TEAMS_BASE}/{team_id}", headers=org_admin_headers)
    assert response.status_code == 200
    assert response.json()["name"] == VALID_TEAM_CREATE["name"]


def test_he365_create_empty_email_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_TEAM_CREATE)
    payload["email"] = ""
    response = client.post(TEAMS_BASE, headers=org_admin_headers, json=payload)
    assert response.status_code == 400


def test_he365_create_duplicate_email_409(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    user_id = UUID("00000000-0000-4000-8000-0000000000d1")
    with Session(sync_engine) as session:
        if session.get(User, user_id) is None:
            session.add(
                User(
                    id=user_id,
                    email="existingcoach@school.edu",
                    username="existingcoachhe365",
                    encrypted_password=hash_password("Coach123!"),
                    role=UserRole.COACH.value,
                    first_name="Existing",
                    last_name="Coach",
                    is_super_admin=False,
                    is_active=True,
                    org_id=SEEDED_ORG_ID,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
    payload = dict(VALID_TEAM_CREATE)
    payload["name"] = "Duplicate Email Team"
    payload["email"] = "existingcoach@school.edu"
    response = client.post(TEAMS_BASE, headers=org_admin_headers, json=payload)
    assert response.status_code == 409


def test_he365_update_team_same_email_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    create = client.post(TEAMS_BASE, headers=org_admin_headers, json=VALID_TEAM_CREATE)
    team_id = create.json()["id"]
    coach_email = VALID_TEAM_CREATE["email"]
    linked_id = UUID("00000000-0000-4000-8000-0000000000d2")
    with Session(sync_engine) as session:
        if session.get(User, linked_id) is None:
            session.add(
                User(
                    id=linked_id,
                    email=coach_email,
                    username="linkedteamcoach365",
                    encrypted_password=hash_password("Coach123!"),
                    role=UserRole.COACH.value,
                    first_name="Linked",
                    last_name="Coach",
                    is_super_admin=False,
                    is_active=True,
                    org_id=SEEDED_ORG_ID,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
    response = client.put(
        f"{TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={"name": "Varsity Elite", "email": coach_email},
    )
    assert response.status_code == 200


def test_he365_team_not_found_404(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(f"{TEAMS_BASE}/{MISSING_TEAM_ID}", headers=org_admin_headers)
    assert response.status_code == 404


def test_he365_create_team_201(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    payload = dict(VALID_TEAM_CREATE)
    payload["name"] = "HE365 Create Team"
    payload["email"] = "he365create@school.edu"
    response = client.post(TEAMS_BASE, headers=org_admin_headers, json=payload)
    assert response.status_code == 201


def test_he365_missing_required_fields_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.post(TEAMS_BASE, headers=org_admin_headers, json={"name": "", "email": "x@y.com"})
    assert response.status_code == 400


def test_he365_update_team_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    create = client.post(TEAMS_BASE, headers=org_admin_headers, json=VALID_TEAM_CREATE)
    team_id = create.json()["id"]
    response = client.put(
        f"{TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={"name": "Updated Name", "email": "updated@school.edu"},
    )
    assert response.status_code == 200


def test_he365_delete_team_204(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    create = client.post(TEAMS_BASE, headers=org_admin_headers, json=VALID_TEAM_CREATE)
    team_id = create.json()["id"]
    response = client.delete(f"{TEAMS_BASE}/{team_id}", headers=org_admin_headers)
    assert response.status_code == 204


def test_he365_duplicate_name_409(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    first = client.post(TEAMS_BASE, headers=org_admin_headers, json=VALID_TEAM_CREATE)
    assert first.status_code == 201
    dup = dict(VALID_TEAM_CREATE)
    dup["email"] = "another@school.edu"
    second = client.post(TEAMS_BASE, headers=org_admin_headers, json=dup)
    assert second.status_code == 409


def test_he365_create_forbidden_403(client: TestClient, seeded_users: dict) -> None:
    headers = auth_headers(create_access_token(REGULAR_USER_ID))
    response = client.post(TEAMS_BASE, headers=headers, json=VALID_TEAM_CREATE)
    assert response.status_code == 403


# --- HE-362 Team Listing (/api/v1/teams — ticket alias /api/organization/team not implemented) ---


def test_he362_list_teams_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(TEAMS_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "items" in body
    assert "pagination" in body


def test_he362_search_teams_by_name_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    client.post(TEAMS_BASE, headers=org_admin_headers, json=VALID_LISTING_CREATE)
    response = client.get(f"{TEAMS_BASE}/search", headers=org_admin_headers, params={"query": "Listing"})
    assert response.status_code == 200
    assert any("Listing" in item["name"] for item in response.json()["items"])


def test_he362_empty_search_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(f"{TEAMS_BASE}/search", headers=org_admin_headers, params={"query": ""})
    assert response.status_code == 400


def test_he362_coach_detail_via_admin_path_200(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(f"{ORG_ADMIN_COACHES_BASE}/{HE_COACH_ID}", headers=org_admin_headers)
    assert response.status_code == 200
    assert response.json()["email"]


def test_he362_list_items_have_active_status(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.get(TEAMS_BASE, headers=org_admin_headers)
    items = response.json()["items"]
    if items:
        assert items[0]["status"] == "active"


def test_he362_create_listing_team_201(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.post(TEAMS_BASE, headers=org_admin_headers, json=VALID_LISTING_CREATE)
    assert response.status_code == 201


def test_he362_missing_required_fields_400(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    response = client.post(TEAMS_BASE, headers=org_admin_headers, json={"name": "Only Name"})
    assert response.status_code == 400


def test_he362_duplicate_name_409(client: TestClient, org_admin_headers: dict[str, str]) -> None:
    first = client.post(TEAMS_BASE, headers=org_admin_headers, json=VALID_LISTING_CREATE)
    assert first.status_code == 201
    second = client.post(TEAMS_BASE, headers=org_admin_headers, json=VALID_LISTING_CREATE)
    assert second.status_code == 409


def test_he362_list_forbidden_403(client: TestClient, seeded_users: dict) -> None:
    headers = auth_headers(create_access_token(REGULAR_USER_ID))
    response = client.get(TEAMS_BASE, headers=headers)
    assert response.status_code == 403
