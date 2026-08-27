"""Cross-ticket acceptance integration tests for coach module APIs (HE-301/305/314/310/318).

Runnable against PostgreSQL with pytest. Relies on tests/conftest.py fixtures:
seeded_users (5 roles), mock_third_party_services, client, coach_headers, etc.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    ADMIN_EMAIL,
    LEADERBOARD_BASE,
    PRACTICE_PLANS_BASE,
    PROFILE_BASE,
    REGULAR_EMAIL,
    SEEDED_FIELD_DRILL_ID,
    SEEDED_FT_DRILL_ID,
    SEEDED_ORG_ID,
    SESSIONS_BASE,
    VIEWER_EMAIL,
    coach_headers,
    expired_user_headers,
    inactive_headers,
    unverified_coach_headers,
    viewer_headers,
)

MODES_URL = f"{SESSIONS_BASE}/modes"
RECORD_URL = f"{SESSIONS_BASE}/record"
SEARCH_URL = f"{LEADERBOARD_BASE}/search"
FILTER_URL = f"{LEADERBOARD_BASE}/filter"


@pytest.fixture(autouse=True)
def _coach_module_tables(
    ensure_practice_sessions_table: None,
    ensure_practice_plans_table: None,
    seed_leaderboard_data: dict,
) -> None:
    """Bootstrap client tables and seed data for cross-ticket tests."""


def _record_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "session_mode": "daily_options",
        "session_details": {"description": "Pick from today's recommended drills"},
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def _plan_payload(name: str = "Acceptance Plan") -> dict[str, object]:
    return {
        "name": name,
        "drills": [{"id": str(SEEDED_FIELD_DRILL_ID), "name": "Spot Up", "type": "shooting"}],
        "phone": "+1-555-0100",
    }


def _profile_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "Lebron",
        "last_name": "James",
        "email": REGULAR_EMAIL,
        "username": "regularcoach",
        "phone_number": "+1 (555) 382-9102",
        "date_of_birth": "08/24/1992",
        "gender": "Male",
        "grade": "Academy Head",
        "parent_guardian": "Not Applicable",
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


# --- HE-301 Session Record ---


def test_he301_post_record_201(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.post(RECORD_URL, headers=coach_headers, json=_record_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["session_mode"] == "daily_options"
    assert body["id"]
    assert body["error"] is None


def test_he301_post_record_missing_mode_returns_validation_error(
    client: TestClient, coach_headers: dict[str, str]
) -> None:
    response = client.post(
        RECORD_URL,
        headers=coach_headers,
        json={"session_details": {"description": "no mode"}, "phone": "+1-555-0100"},
    )
    assert response.status_code in (400, 422)
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_he301_post_record_409_duplicate_session(
    client: TestClient, coach_headers: dict[str, str]
) -> None:
    assert client.post(RECORD_URL, headers=coach_headers, json=_record_payload()).status_code == 201
    dup = client.post(RECORD_URL, headers=coach_headers, json=_record_payload(session_mode="one_drill"))
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "SESSION_MODE_ALREADY_RECORDED"


def test_he301_get_modes_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.get(MODES_URL, headers=coach_headers)
    assert response.status_code == 200
    modes = {m["mode"] for m in response.json()["modes"]}
    assert modes == {"one_drill", "daily_options", "practice_plan"}


def test_he301_get_mode_404(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.get(f"{MODES_URL}/does-not-exist", headers=coach_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_MODE_NOT_FOUND"


def test_he301_put_record_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    created = client.post(RECORD_URL, headers=coach_headers, json=_record_payload())
    session_id = created.json()["id"]
    response = client.put(
        f"{RECORD_URL}/{session_id}",
        headers=coach_headers,
        json={"session_mode": "practice_plan", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    assert response.json()["session_mode"] == "practice_plan"


def test_he301_modes_401_missing_token(client: TestClient) -> None:
    assert client.get(MODES_URL).status_code == 401


def test_he301_record_403_unverified_coach(client: TestClient, unverified_coach_headers: dict[str, str]) -> None:
    response = client.post(RECORD_URL, headers=unverified_coach_headers, json=_record_payload())
    assert response.status_code == 403


# --- HE-305 Session Summary ---


def test_he305_get_summary_200(
    client: TestClient, coach_headers: dict[str, str], seed_session_summary_data: dict
) -> None:
    session_id = seed_session_summary_data["session_id"]
    response = client.get(f"{SESSIONS_BASE}/{session_id}", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["session_time"] == "9:41"
    assert body["player_stats"][0]["player_name"] == "Charlie Hudson"


def test_he305_get_summary_404(client: TestClient, coach_headers: dict[str, str]) -> None:
    missing = "00000000-0000-4000-8000-000000000099"
    assert client.get(f"{SESSIONS_BASE}/{missing}", headers=coach_headers).status_code == 404


def test_he305_next_drill_200(
    client: TestClient, coach_headers: dict[str, str], seed_session_summary_data: dict
) -> None:
    session_id = seed_session_summary_data["session_id"]
    response = client.post(
        f"{SESSIONS_BASE}/{session_id}/next-drill",
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    assert response.json()["current_drill_index"] == 1


def test_he305_end_practice_200(
    client: TestClient, coach_headers: dict[str, str], seed_session_summary_data: dict
) -> None:
    session_id = seed_session_summary_data["session_id"]
    response = client.post(
        f"{SESSIONS_BASE}/{session_id}/end-practice",
        headers=coach_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Session Complete! Nice work, coach"


def test_he305_get_summary_403_other_coach(
    client: TestClient, seed_session_summary_data: dict
) -> None:
    session_id = seed_session_summary_data["session_id"]
    response = client.get(
        f"{SESSIONS_BASE}/{session_id}",
        headers=seed_session_summary_data["other_coach_headers"],
    )
    assert response.status_code == 403


# --- HE-314 Leaderboard ---


def test_he314_get_leaderboard_200_public(client: TestClient) -> None:
    response = client.get(LEADERBOARD_BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["items"]) >= 1
    assert "shooting_percent" in body["items"][0]


def test_he314_post_search_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.post(
        SEARCH_URL,
        headers=coach_headers,
        json={"search_query": "Jane", "full_name": "Jane Doe", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["full_name"] == "Jane Doe"


def test_he314_get_filter_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.get(
        FILTER_URL, headers=coach_headers, params={"filter_metric": "shooting_percent"}
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["rank"] == 1


def test_he314_get_search_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.get(SEARCH_URL, headers=coach_headers, params={"search_query": "Charlie"})
    assert response.status_code == 200
    assert response.json()["items"][0]["full_name"] == "Charlie Hudson"


def test_he314_get_search_400_empty(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.get(SEARCH_URL, headers=coach_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_he314_search_401(client: TestClient) -> None:
    assert client.post(SEARCH_URL, json={"search_query": "Jane"}).status_code == 401


def test_he314_leaderboard_top_player_ranked_first(client: TestClient, coach_headers: dict[str, str]) -> None:
    """Jane Doe has 80% shooting — should rank first when filtered by shooting_percent."""
    response = client.get(
        FILTER_URL, headers=coach_headers, params={"filter_metric": "shooting_percent"}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["full_name"] == "Jane Doe"
    assert items[0]["shooting_percent"] == 80


# --- HE-310 Practice Plans ---


def test_he310_create_201(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=_plan_payload())
    assert response.status_code == 201
    assert response.json()["name"] == "Acceptance Plan"


def test_he310_create_409_duplicate(client: TestClient, coach_headers: dict[str, str]) -> None:
    payload = _plan_payload("Duplicate Plan")
    assert client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=payload).status_code == 201
    dup = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=payload)
    assert dup.status_code == 409


def test_he310_list_active_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json=_plan_payload("Listed Plan"))
    response = client.get(PRACTICE_PLANS_BASE, headers=coach_headers)
    assert response.status_code == 200
    assert any(p["name"] == "Listed Plan" for p in response.json()["plans"])


def test_he310_update_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    plan_id = client.post(
        PRACTICE_PLANS_BASE, headers=coach_headers, json=_plan_payload("Before Update")
    ).json()["id"]
    response = client.put(
        f"{PRACTICE_PLANS_BASE}/{plan_id}",
        headers=coach_headers,
        json={"name": "After Update", "drills": _plan_payload()["drills"]},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "After Update"


def test_he310_update_400_invalid(client: TestClient, coach_headers: dict[str, str]) -> None:
    plan_id = client.post(
        PRACTICE_PLANS_BASE, headers=coach_headers, json=_plan_payload("Invalid Update Target")
    ).json()["id"]
    response = client.put(
        f"{PRACTICE_PLANS_BASE}/{plan_id}",
        headers=coach_headers,
        json={"name": "   "},
    )
    assert response.status_code == 400


def test_he310_delete_204(client: TestClient, coach_headers: dict[str, str]) -> None:
    plan_id = client.post(
        PRACTICE_PLANS_BASE, headers=coach_headers, json=_plan_payload("To Delete")
    ).json()["id"]
    assert client.delete(f"{PRACTICE_PLANS_BASE}/{plan_id}", headers=coach_headers).status_code == 204
    assert client.get(PRACTICE_PLANS_BASE, headers=coach_headers).json()["plans"] == []


def test_he310_create_422_missing_fields(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.post(PRACTICE_PLANS_BASE, headers=coach_headers, json={"phone": "+1-555-0100"})
    assert response.status_code in (400, 422)


def test_he310_update_404(client: TestClient, coach_headers: dict[str, str]) -> None:
    missing = "00000000-0000-4000-8000-000000000099"
    assert (
        client.put(
            f"{PRACTICE_PLANS_BASE}/{missing}",
            headers=coach_headers,
            json={"name": "Ghost"},
        ).status_code
        == 404
    )


def test_he310_delete_404(client: TestClient, coach_headers: dict[str, str]) -> None:
    missing = "00000000-0000-4000-8000-000000000099"
    assert client.delete(f"{PRACTICE_PLANS_BASE}/{missing}", headers=coach_headers).status_code == 404


def test_he310_401_without_auth(client: TestClient) -> None:
    assert client.get(PRACTICE_PLANS_BASE).status_code == 401


# --- HE-318 Edit Profile ---


def test_he318_get_profile_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.get(PROFILE_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == REGULAR_EMAIL
    assert body["profile"]["first_name"] == body["first_name"]


def test_he318_put_profile_200_all_fields(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.put(PROFILE_BASE, headers=coach_headers, json=_profile_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Lebron"
    assert body["date_of_birth"] == "08/24/1992"
    assert body["parent_guardian"] == "Not Applicable"


def test_he318_put_profile_400_empty_first_name(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.put(
        PROFILE_BASE, headers=coach_headers, json=_profile_payload(first_name="   ")
    )
    assert response.status_code == 400


def test_he318_put_profile_409_duplicate_email(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.put(
        PROFILE_BASE, headers=coach_headers, json=_profile_payload(email=ADMIN_EMAIL)
    )
    assert response.status_code == 409


def test_he318_put_profile_400_invalid_phone(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.put(
        PROFILE_BASE, headers=coach_headers, json=_profile_payload(phone_number="not-a-phone")
    )
    assert response.status_code == 400


def test_he318_put_profile_400_invalid_email(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.put(
        PROFILE_BASE, headers=coach_headers, json=_profile_payload(email="bad-email")
    )
    assert response.status_code == 400


def test_he318_put_profile_409_duplicate_username(
    client: TestClient, coach_headers: dict[str, str], viewer_headers: dict[str, str]
) -> None:
    client.put(
        PROFILE_BASE,
        headers=viewer_headers,
        json={"first_name": "Viewer", "last_name": "Player", "email": VIEWER_EMAIL, "username": "takenname"},
    )
    response = client.put(
        PROFILE_BASE, headers=coach_headers, json=_profile_payload(username="takenname")
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USERNAME_ALREADY_IN_USE"


def test_he318_put_profile_422_missing_required(client: TestClient, coach_headers: dict[str, str]) -> None:
    response = client.put(PROFILE_BASE, headers=coach_headers, json={"phone": "+1-555-0100"})
    assert response.status_code in (400, 422)


def test_he318_put_profile_400_invalid_date_of_birth(
    client: TestClient, coach_headers: dict[str, str]
) -> None:
    response = client.put(
        PROFILE_BASE, headers=coach_headers, json=_profile_payload(date_of_birth="1992-08-24")
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "date_of_birth"


def test_he318_profile_401_expired_token(client: TestClient, expired_user_headers: dict[str, str]) -> None:
    assert client.get(PROFILE_BASE, headers=expired_user_headers).status_code == 401


def test_he318_profile_401_inactive_user(client: TestClient, inactive_headers: dict[str, str]) -> None:
    assert client.get(PROFILE_BASE, headers=inactive_headers).status_code == 401
