"""Runnable integration tests for HE-367, HE-404, HE-424, and HE-413 acceptance criteria.

Uses PostgreSQL test infrastructure from tests/conftest.py. All third-party integrations
are avoided; support contact persists to the local staging table only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.org_admin_team import TEAM_REMOVAL_CONFIRMATION_MESSAGE
from tests.conftest import (
    ORG_ADMIN_EDIT_PLAYERS_BASE,
    ORG_ADMIN_LEADERBOARD_BASE,
    ORG_ADMIN_SUPPORT_CONTACT_BASE,
    ORG_ADMIN_TEAMS_BASE,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

pytest_plugins = ["tests.fixtures.org_admin_acceptance_fixtures"]

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000090")
MISSING_TEAM_ID = UUID("00000000-0000-4000-8000-000000999998")
PLAYER_DETAIL_ID = UUID("00000000-0000-4000-8000-000000000036")
SEARCH_URL = f"{ORG_ADMIN_LEADERBOARD_BASE}/search"
FILTERS_URL = f"{ORG_ADMIN_LEADERBOARD_BASE}/filters"
CONFIRMATION_URL = f"{ORG_ADMIN_SUPPORT_CONTACT_BASE}/confirmation"

VALID_TEAM_CREATE = {
    "team_name": "Acceptance Varsity",
    "team_code": "AV-2026",
    "team_description": "Acceptance test roster",
    "age_group": "16-18",
    "coaches": [],
    "full_name": "Acceptance Varsity",
    "phone": "+1-555-0100",
}
VALID_REMOVAL_PAYLOAD = {"phone": "+1-555-0100"}
VALID_SUPPORT_PAYLOAD = {
    "email": "acceptance.support@example.com",
    "phone": "+15558392001",
    "inquiry_subject": "Technical Issue",
    "message_description": "Acceptance test support inquiry body.",
}


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Organization admin JWT for acceptance tests."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.acceptance@test.com",
                    username="orgadminacceptance",
                    encrypted_password=hash_password("OrgAdmin123!"),
                    role=UserRole.ORG_ADMIN.value,
                    first_name="Acceptance",
                    last_name="Admin",
                    is_super_admin=False,
                    is_active=True,
                    org_id=SEEDED_ORG_ID,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
    return auth_headers(create_access_token(ORG_ADMIN_ID))


@pytest.fixture
def coach_headers(seeded_users: dict) -> dict[str, str]:
    return auth_headers(create_access_token(REGULAR_USER_ID))


@pytest.fixture(autouse=True)
def _clean_support_requests() -> None:
    with sync_engine.begin() as connection:
        connection.execute(text("DELETE FROM support_requests_staging"))


def _create_team(client: TestClient, headers: dict[str, str], *, code: str) -> str:
    response = client.post(
        ORG_ADMIN_TEAMS_BASE,
        headers=headers,
        json={**VALID_TEAM_CREATE, "team_code": code},
    )
    assert response.status_code == 201
    return response.json()["id"]


# --- HE-367: Remove Team ---


def test_he367_ac_remove_team_200_confirmation_message(
    client: TestClient,
    org_admin_headers: dict[str, str],
    ensure_teams_table: None,
) -> None:
    team_id = _create_team(client, org_admin_headers, code="HE367-OK")
    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Team removed successfully"
    assert body["status"] == "removed"
    assert body["team_id"] == team_id


def test_he367_ac_remove_team_404_not_found(
    client: TestClient,
    org_admin_headers: dict[str, str],
    ensure_teams_table: None,
) -> None:
    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{MISSING_TEAM_ID}",
        headers=org_admin_headers,
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TEAM_NOT_FOUND"


def test_he367_ac_remove_team_403_non_admin(
    client: TestClient,
    coach_headers: dict[str, str],
    ensure_teams_table: None,
) -> None:
    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{MISSING_TEAM_ID}",
        headers=coach_headers,
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_he367_ac_remove_team_400_missing_phone(
    client: TestClient,
    org_admin_headers: dict[str, str],
    ensure_teams_table: None,
) -> None:
    team_id = _create_team(client, org_admin_headers, code="HE367-NOPHONE")
    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
        json={"phone": "   "},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"][0]["field"] == "phone"


def test_he367_ac_get_team_200_with_confirmation_message(
    client: TestClient,
    org_admin_headers: dict[str, str],
    ensure_teams_table: None,
) -> None:
    team_id = _create_team(client, org_admin_headers, code="HE367-GET")
    response = client.get(f"{ORG_ADMIN_TEAMS_BASE}/{team_id}", headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == team_id
    assert body["name"] == "Acceptance Varsity"
    assert body["confirmation_message"] == TEAM_REMOVAL_CONFIRMATION_MESSAGE
    assert body["organization"] == "Seeded Hoops Club"


def test_he367_edge_remove_team_401_missing_token(
    client: TestClient,
    ensure_teams_table: None,
) -> None:
    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{MISSING_TEAM_ID}",
        json=VALID_REMOVAL_PAYLOAD,
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_he367_edge_remove_team_422_missing_body(
    client: TestClient,
    org_admin_headers: dict[str, str],
    ensure_teams_table: None,
) -> None:
    team_id = _create_team(client, org_admin_headers, code="HE367-NOBODY")
    response = client.delete(
        f"{ORG_ADMIN_TEAMS_BASE}/{team_id}",
        headers=org_admin_headers,
    )
    assert response.status_code == 422


# --- HE-404: Leaderboard ---


def test_he404_ac_leaderboard_200_org_admin(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(ORG_ADMIN_LEADERBOARD_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["organization"] == "Seeded Hoops Club"
    assert len(body["items"]) >= 1
    assert "shooting_percent" in body["items"][0]


def test_he404_ac_leaderboard_search_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(
        SEARCH_URL,
        headers=org_admin_headers,
        params={"search_query": "Jane", "full_name": "Jane Doe"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["items"]) >= 1
    assert body["items"][0]["full_name"] == "Jane Doe"


def test_he404_ac_leaderboard_filters_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.post(
        FILTERS_URL,
        headers=org_admin_headers,
        json={
            "filters": {
                "ranking": "top",
                "date_range": {"start": "2020-01-01", "end": "2030-12-31"},
            },
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Leaderboard filtered successfully"
    assert len(body["items"]) >= 1


def test_he404_ac_leaderboard_403_non_admin(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(ORG_ADMIN_LEADERBOARD_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_he404_ac_leaderboard_search_400_empty_query(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(SEARCH_URL, headers=org_admin_headers, params={"search_query": "  "})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_he404_edge_leaderboard_401_missing_token(
    client: TestClient,
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(ORG_ADMIN_LEADERBOARD_BASE)
    assert response.status_code == 401


def test_he404_edge_leaderboard_search_invalid_phone_400(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    response = client.get(
        SEARCH_URL,
        headers=org_admin_headers,
        params={"search_query": "Jane", "phone": "not-a-phone"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "phone"


# --- HE-424: Player Listing ---


def test_he424_ac_list_players_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.get(ORG_ADMIN_EDIT_PLAYERS_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["organization"] == "Seeded Hoops Club"
    assert len(body["players"]) >= 1
    assert all(player["status"] == "active" for player in body["players"])


def test_he424_ac_search_players_by_code_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.post(
        f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/search",
        headers=org_admin_headers,
        json={"player_code": "PC-AVA001", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["player_code"] == "PC-AVA001"
    assert len(body["players"]) == 1
    assert body["players"][0]["name"] == "Ava Morales"
    assert body["players"][0]["code"] == "PC-AVA001"


def test_he424_ac_update_player_200_persists(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.put(
        f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=org_admin_headers,
        json={"full_name": "Updated Ava Morales", "email": "updated.ava@school.edu"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Ava Morales"

    verify = client.get(
        f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{PLAYER_DETAIL_ID}",
        headers=org_admin_headers,
    )
    assert verify.status_code == 200
    assert verify.json()["full_name"] == "Updated Ava Morales"
    assert verify.json()["email"] == "updated.ava@school.edu"


def test_he424_ac_players_403_non_admin(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.get(ORG_ADMIN_EDIT_PLAYERS_BASE, headers=coach_headers)
    assert response.status_code == 403


def test_he424_ac_players_400_missing_fields(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.post(
        f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/search",
        headers=org_admin_headers,
        json={"player_code": ""},
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "player_code"


def test_he424_edge_players_401_missing_token(
    client: TestClient,
    seed_org_admin_players: None,
) -> None:
    response = client.get(ORG_ADMIN_EDIT_PLAYERS_BASE)
    assert response.status_code == 401


def test_he424_edge_update_player_status_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
    seed_org_admin_players: None,
) -> None:
    response = client.patch(
        f"{ORG_ADMIN_EDIT_PLAYERS_BASE}/{PLAYER_DETAIL_ID}/status",
        headers=org_admin_headers,
        json={"status": "inactive", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "inactive"


# --- HE-413: Contact Support ---


def test_he413_ac_support_contact_201(
    client: TestClient,
) -> None:
    response = client.post(ORG_ADMIN_SUPPORT_CONTACT_BASE, json=VALID_SUPPORT_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Your support request has been submitted successfully"
    assert body["id"] == body["request_id"]
    assert "id" in body


def test_he413_ac_support_contact_400_missing_email(
    client: TestClient,
) -> None:
    response = client.post(
        ORG_ADMIN_SUPPORT_CONTACT_BASE,
        json={**VALID_SUPPORT_PAYLOAD, "email": ""},
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "email"


def test_he413_ac_support_contact_400_invalid_email(
    client: TestClient,
) -> None:
    response = client.post(
        ORG_ADMIN_SUPPORT_CONTACT_BASE,
        json={**VALID_SUPPORT_PAYLOAD, "email": "bad-email"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "email"


def test_he413_ac_support_contact_400_message_too_long(
    client: TestClient,
) -> None:
    response = client.post(
        ORG_ADMIN_SUPPORT_CONTACT_BASE,
        json={**VALID_SUPPORT_PAYLOAD, "message_description": "x" * 501},
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "message_description"


def test_he413_ac_support_contact_400_missing_required_fields(
    client: TestClient,
) -> None:
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


def test_he413_edge_confirmation_401_without_auth(
    client: TestClient,
) -> None:
    created = client.post(ORG_ADMIN_SUPPORT_CONTACT_BASE, json=VALID_SUPPORT_PAYLOAD)
    request_id = created.json()["id"]
    response = client.get(CONFIRMATION_URL, params={"request_id": request_id})
    assert response.status_code == 401


def test_he413_edge_confirmation_200_with_org_admin(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    created = client.post(ORG_ADMIN_SUPPORT_CONTACT_BASE, json=VALID_SUPPORT_PAYLOAD)
    request_id = created.json()["id"]
    response = client.get(
        CONFIRMATION_URL,
        headers=org_admin_headers,
        params={"request_id": request_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == VALID_SUPPORT_PAYLOAD["email"]
    assert body["inquiry_subject"] == "Technical Issue"
