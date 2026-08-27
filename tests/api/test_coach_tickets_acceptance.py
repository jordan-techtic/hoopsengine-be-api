"""Cross-ticket acceptance integration tests (HE-300, HE-302, HE-303, HE-304, HE-321, HE-324, HE-329).

Each test function name references the ticket key. All tests use PostgreSQL via tests/conftest.py;
SendGrid and Stripe are mocked globally in conftest mock_third_party_services.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import (
    COACH_DRILLS_BASE,
    COACH_QUEUE_BASE,
    DRILL_IDEAS_BASE,
    DRILLS_BASE,
    LIVE_PRACTICE_BASE,
    REGULAR_USER_ID,
    SEEDED_FIELD_DRILL_ID,
    SEEDED_ORG_ID,
    SEEDED_PLAYER_ID,
    SEEDED_PLAYER_JANE_ID,
    SESSIONS_BASE,
    sync_engine,
)

RECORD_URL = f"{SESSIONS_BASE}/record"


@pytest.fixture(autouse=True)
def _tables(ensure_practice_plans_table: None, ensure_practice_sessions_table: None) -> None:
    with sync_engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS drill_submissions (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                org_id uuid, submitted_by uuid, drill_name text NOT NULL,
                category text, description text, directions text,
                status text DEFAULT 'pending', submitted_at timestamptz DEFAULT now()
            )
            """
        ))
        conn.execute(text("DELETE FROM drill_submissions"))


def _record_payload(**overrides: object) -> dict[str, object]:
    base = {
        "session_mode": "one_drill",
        "drill_id": str(SEEDED_FIELD_DRILL_ID),
        "session_data": {"reps": 10, "time": "00:30:00", "performance": "good"},
        "phone": "+1-555-0100",
    }
    base.update(overrides)
    return base


def _seed_wizard_session() -> None:
    flow = {"one_drill_flow": {"step": 2, "selected_player_id": str(SEEDED_PLAYER_JANE_ID)}}
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM practice_sessions"))
        conn.execute(
            text(
                """
                INSERT INTO practice_sessions (
                    id, org_id, session_date, session_mode, session_details,
                    recorder_user_id, status, synced
                ) VALUES (
                    :id, :org_id, CURRENT_DATE, 'one_drill', CAST(:d AS jsonb),
                    :uid, 'in_progress', true
                )
                """
            ),
            {
                "id": "00000000-0000-4000-8000-000000000060",
                "org_id": SEEDED_ORG_ID,
                "d": json.dumps(flow),
                "uid": REGULAR_USER_ID,
            },
        )


# HE-303
def test_he303_continue_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    _seed_wizard_session()
    r = client.post(f"{DRILLS_BASE}/continue", headers=coach_headers, json={"selected_drill_id": str(SEEDED_FIELD_DRILL_ID)})
    assert r.status_code == 200 and r.json()["step"] == 3


def test_he303_search_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    r = client.get(f"{DRILLS_BASE}?search=warm", headers=coach_headers)
    assert r.status_code == 200 and any("warm" in d["name"].lower() for d in r.json()["drills"])


def test_he303_validation_400(client: TestClient, coach_headers: dict[str, str]) -> None:
    _seed_wizard_session()
    r = client.post(f"{DRILLS_BASE}/continue", headers=coach_headers, json={})
    assert r.status_code == 422


def test_he303_duplicate_409(client: TestClient, coach_headers: dict[str, str]) -> None:
    p = {"drill_name": "AC303 Unique", "drill_category": "shooting"}
    assert client.post(DRILLS_BASE, headers=coach_headers, json=p).status_code == 201
    assert client.post(DRILLS_BASE, headers=coach_headers, json=p).status_code == 409


@pytest.fixture
def seed_step3_support_data() -> None:
    with sync_engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS players (id uuid PRIMARY KEY, org_id uuid, first_name text, last_name text, player_code text UNIQUE, active boolean DEFAULT true)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS drills (id uuid PRIMARY KEY, name text NOT NULL, category text NOT NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS session_data (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), session_id uuid, org_id uuid, player_id uuid, drill_id uuid, makes int DEFAULT 0, attempts int DEFAULT 0, synced boolean DEFAULT true)"))
        conn.execute(text("INSERT INTO players (id, org_id, first_name, last_name, player_code) VALUES (:id, :org, 'Charlie', 'Hudson', 'PC1') ON CONFLICT (id) DO UPDATE SET first_name = EXCLUDED.first_name, last_name = EXCLUDED.last_name"), {"id": SEEDED_PLAYER_ID, "org": SEEDED_ORG_ID})
        conn.execute(text("INSERT INTO drills (id, name, category) VALUES (:id, '3-Point Shooting', 'shooting') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, category = EXCLUDED.category"), {"id": SEEDED_FIELD_DRILL_ID})


@pytest.fixture
def seed_live_practice_tables() -> None:
    with sync_engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS drills (id uuid PRIMARY KEY, name text UNIQUE, category text NOT NULL, time_seconds integer, submitted_by_org uuid, approved boolean DEFAULT true)"))
        conn.execute(text("DELETE FROM drills WHERE category = 'live_practice'"))


# HE-304
def test_he304_create_201(client: TestClient, coach_headers: dict[str, str], seed_step3_support_data: None) -> None:
    r = client.post(SESSIONS_BASE, headers=coach_headers, json={"player": "Charlie Hudson", "drill": "3-Point Shooting", "makes": 5, "attempts": 10, "phone": "+1-555-0100"})
    assert r.status_code == 201 and r.json()["makes"] == 5


def test_he304_missing_fields_400(client: TestClient, coach_headers: dict[str, str], seed_step3_support_data: None) -> None:
    assert client.post(SESSIONS_BASE, headers=coach_headers, json={"player": "", "drill": "3-Point Shooting", "makes": 1, "attempts": 2}).status_code == 400


def test_he304_update_200(client: TestClient, coach_headers: dict[str, str], seed_step3_support_data: None) -> None:
    sid = client.post(SESSIONS_BASE, headers=coach_headers, json={"player": "Charlie Hudson", "drill": "3-Point Shooting", "makes": 5, "attempts": 10}).json()["id"]
    r = client.put(f"{SESSIONS_BASE}/{sid}", headers=coach_headers, json={"makes": 8, "attempts": 12})
    assert r.status_code == 200 and r.json()["makes"] == 8


def test_he304_get_by_id_200(client: TestClient, coach_headers: dict[str, str], seed_step3_support_data: None) -> None:
    sid = client.post(SESSIONS_BASE, headers=coach_headers, json={"player": "Charlie Hudson", "drill": "3-Point Shooting", "makes": 5, "attempts": 10}).json()["id"]
    r = client.get(f"{SESSIONS_BASE}/{sid}", headers=coach_headers)
    assert r.status_code == 200 and r.json()["drill"] == "3-Point Shooting"


def test_he304_summary_200(client: TestClient, coach_headers: dict[str, str], seed_step3_support_data: None) -> None:
    client.post(SESSIONS_BASE, headers=coach_headers, json={"player": "Charlie Hudson", "drill": "3-Point Shooting", "makes": 5, "attempts": 10})
    r = client.get(f"{SESSIONS_BASE}/summary", headers=coach_headers)
    assert r.status_code == 200 and len(r.json()["sessions"]) >= 1


# HE-324
def test_he324_search_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    r = client.post(f"{COACH_DRILLS_BASE}/search", headers=coach_headers, json={"search_query": "Jane"})
    assert r.status_code == 200 and r.json()["players"]


def test_he324_search_empty_400(client: TestClient, coach_headers: dict[str, str]) -> None:
    assert client.post(f"{COACH_DRILLS_BASE}/search", headers=coach_headers, json={"search_query": ""}).status_code == 400


def test_he324_select_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    r = client.post(f"{COACH_DRILLS_BASE}/select_player", headers=coach_headers, json={"selected_player_id": str(SEEDED_PLAYER_JANE_ID)})
    assert r.status_code == 200


def test_he324_select_missing_409(client: TestClient, coach_headers: dict[str, str]) -> None:
    r = client.post(f"{COACH_DRILLS_BASE}/select_player", headers=coach_headers, json={"selected_player_id": "00000000-0000-4000-8000-000000000099"})
    assert r.status_code == 409


def test_he324_continue_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    client.post(f"{COACH_DRILLS_BASE}/select_player", headers=coach_headers, json={"selected_player_id": str(SEEDED_PLAYER_JANE_ID)})
    r = client.post(f"{COACH_DRILLS_BASE}/continue", headers=coach_headers, json={})
    assert r.status_code == 200 and r.json()["step"] == 2


# HE-321
def test_he321_submit_201(client: TestClient, coach_headers: dict[str, str]) -> None:
    r = client.post(DRILL_IDEAS_BASE, headers=coach_headers, json={"drill_name": "AC321 Idea", "category": "Shooting", "difficulty_level": "Beginner", "instructions": "Run the break."})
    assert r.status_code == 201 and r.json()["status"] == "submitted"


def test_he321_missing_name_400(client: TestClient, coach_headers: dict[str, str]) -> None:
    assert client.post(DRILL_IDEAS_BASE, headers=coach_headers, json={"drill_name": "", "category": "S", "difficulty_level": "Beginner", "instructions": "x"}).status_code == 400


def test_he321_invalid_difficulty_400(client: TestClient, coach_headers: dict[str, str]) -> None:
    r = client.post(DRILL_IDEAS_BASE, headers=coach_headers, json={"drill_name": "X", "category": "S", "difficulty_level": "Expert", "instructions": "x"})
    assert r.status_code == 400


def test_he321_list_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    assert client.get(DRILL_IDEAS_BASE, headers=coach_headers).status_code == 200


def test_he321_catalog_drill_201(client: TestClient, coach_headers: dict[str, str]) -> None:
    r = client.post(DRILLS_BASE, headers=coach_headers, json={"drill_name": "AC321 Catalog", "drill_category": "shooting"})
    assert r.status_code == 201


def test_he321_empty_drill_name_400(client: TestClient, coach_headers: dict[str, str]) -> None:
    assert client.post(DRILLS_BASE, headers=coach_headers, json={"drill_name": "", "drill_category": "shooting"}).status_code == 400


def test_he321_duplicate_409(client: TestClient, coach_headers: dict[str, str]) -> None:
    p = {
        "drill_name": "AC321 Dup Idea",
        "category": "Shooting",
        "difficulty_level": "Beginner",
        "instructions": "Duplicate submission test.",
    }
    assert client.post(DRILL_IDEAS_BASE, headers=coach_headers, json=p).status_code == 201
    assert client.post(DRILL_IDEAS_BASE, headers=coach_headers, json=p).status_code == 409


def test_he321_required_fields_400(client: TestClient, coach_headers: dict[str, str]) -> None:
    assert client.post(DRILL_IDEAS_BASE, headers=coach_headers, json={"drill_name": "N", "category": "", "difficulty_level": "Beginner", "instructions": "i"}).status_code == 400


def test_he321_unauthorized_403(client: TestClient, viewer_headers: dict[str, str]) -> None:
    assert client.post(DRILL_IDEAS_BASE, headers=viewer_headers, json={"drill_name": "N", "category": "S", "difficulty_level": "Beginner", "instructions": "i"}).status_code == 403


# HE-329
def test_he329_get_queue_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    with sync_engine.begin() as conn:
        conn.execute(text("DELETE FROM practice_sessions"))
        conn.execute(text(
            """
            INSERT INTO practice_sessions (id, org_id, session_date, session_mode, recorder_user_id, recorder_type, status, synced)
            VALUES ('00000000-0000-4000-8000-000000000070', :org, CURRENT_DATE, 'one_drill', :uid, 'coach', 'in_progress', false)
            """
        ), {"org": SEEDED_ORG_ID, "uid": REGULAR_USER_ID})
    r = client.get(COACH_QUEUE_BASE, headers=coach_headers)
    assert r.status_code == 200 and r.json()["items"]


def test_he329_post_update_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    with sync_engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS session_data (
                id uuid PRIMARY KEY, session_id uuid, org_id uuid NOT NULL,
                player_id uuid NOT NULL, drill_id uuid, makes int DEFAULT 0, attempts int DEFAULT 0,
                session_date date DEFAULT CURRENT_DATE, synced boolean DEFAULT false
            )
            """
        ))
        conn.execute(text("DELETE FROM session_data"))
        conn.execute(text(
            """
            INSERT INTO session_data (id, session_id, org_id, player_id, drill_id, synced)
            VALUES ('00000000-0000-4000-8000-000000000071', '00000000-0000-4000-8000-000000000070', :org, :pid, :did, false)
            """
        ), {"org": SEEDED_ORG_ID, "pid": SEEDED_PLAYER_ID, "did": SEEDED_FIELD_DRILL_ID})
    r = client.post(COACH_QUEUE_BASE, headers=coach_headers, json={"item_id": "00000000-0000-4000-8000-000000000071", "item_type": "session_data", "status": "synced"})
    assert r.status_code == 200


def test_he329_get_invalid_filter_400(client: TestClient, coach_headers: dict[str, str]) -> None:
    assert client.get(f"{COACH_QUEUE_BASE}?status_filter=bad", headers=coach_headers).status_code == 400


# HE-300
def test_he300_record_201(client: TestClient, coach_headers: dict[str, str]) -> None:
    r = client.post(RECORD_URL, headers=coach_headers, json=_record_payload())
    assert r.status_code == 201 and r.json()["status"] == "completed"


def test_he300_missing_fields_400(client: TestClient, coach_headers: dict[str, str]) -> None:
    p = _record_payload()
    del p["drill_id"]
    assert client.post(RECORD_URL, headers=coach_headers, json=p).status_code == 400


def test_he300_duplicate_409(client: TestClient, coach_headers: dict[str, str]) -> None:
    assert client.post(RECORD_URL, headers=coach_headers, json=_record_payload()).status_code == 201
    assert client.post(RECORD_URL, headers=coach_headers, json=_record_payload()).status_code == 409


def test_he300_list_drills_200(client: TestClient, coach_headers: dict[str, str]) -> None:
    r = client.get(DRILLS_BASE, headers=coach_headers)
    assert r.status_code == 200 and r.json()["drills"][0]["id"]


def test_he300_invalid_mode_422(client: TestClient, coach_headers: dict[str, str]) -> None:
    assert client.post(RECORD_URL, headers=coach_headers, json=_record_payload(session_mode="bad_mode")).status_code == 422


# HE-302
def test_he302_save_drill_201(client: TestClient, coach_headers: dict[str, str], seed_live_practice_tables: None) -> None:
    r = client.post(f"{LIVE_PRACTICE_BASE}/drills", headers=coach_headers, json={"drill_name": "AC302 Drill", "duration": 45})
    assert r.status_code == 201


def test_he302_missing_fields_400(client: TestClient, coach_headers: dict[str, str], seed_live_practice_tables: None) -> None:
    assert (
        client.post(
            f"{LIVE_PRACTICE_BASE}/drills",
            headers=coach_headers,
            json={"drill_name": "", "duration": 60},
        ).status_code
        == 400
    )


def test_he302_duplicate_409(client: TestClient, coach_headers: dict[str, str], seed_live_practice_tables: None) -> None:
    p = {"drill_name": "AC302 Dup", "duration": 30}
    client.post(f"{LIVE_PRACTICE_BASE}/drills", headers=coach_headers, json=p)
    assert client.post(f"{LIVE_PRACTICE_BASE}/drills", headers=coach_headers, json=p).status_code == 409


def test_he302_player_validation_400(client: TestClient, coach_headers: dict[str, str], seed_live_practice_tables: None) -> None:
    r = client.post(f"{LIVE_PRACTICE_BASE}/players/{SEEDED_PLAYER_JANE_ID}/shots", headers=coach_headers, json={"shots_made": 10, "shots_attempted": 5})
    assert r.status_code == 400


def test_he302_unauthorized_403(client: TestClient, viewer_headers: dict[str, str], seed_live_practice_tables: None) -> None:
    assert client.post(f"{LIVE_PRACTICE_BASE}/drills", headers=viewer_headers, json={"drill_name": "X", "duration": 30}).status_code == 403


def test_he302_timer_200(client: TestClient, coach_headers: dict[str, str], seed_live_practice_tables: None) -> None:
    assert client.post(f"{LIVE_PRACTICE_BASE}/timer/start", headers=coach_headers, json={"duration": 60}).json()["timer_state"] == "running"
    assert client.post(f"{LIVE_PRACTICE_BASE}/timer/stop", headers=coach_headers, json={}).json()["timer_state"] == "stopped"


def test_he302_statistics_200(client: TestClient, coach_headers: dict[str, str], seed_live_practice_tables: None) -> None:
    client.post(f"{LIVE_PRACTICE_BASE}/players/{SEEDED_PLAYER_JANE_ID}/shots", headers=coach_headers, json={"shots_made": 4, "shots_attempted": 8})
    r = client.get(f"{LIVE_PRACTICE_BASE}/players/{SEEDED_PLAYER_JANE_ID}/statistics")
    assert r.status_code == 200 and r.json()["shots_made"] == 4


# Auth 401
@pytest.mark.parametrize("method,url,body", [
    ("get", DRILLS_BASE, None),
    ("post", RECORD_URL, {"session_mode": "one_drill", "drill_id": "00000000-0000-4000-8000-000000000031", "session_data": {"reps": 1, "time": "00:01:00", "performance": "ok"}}),
])
def test_auth_401_missing_token(client: TestClient, method: str, url: str, body: dict | None) -> None:
    r = client.get(url) if method == "get" else client.post(url, json=body)
    assert r.status_code == 401
