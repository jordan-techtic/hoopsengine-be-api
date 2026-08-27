"""Integration tests for coach home screen APIs (HE-299)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.coach_home import NOTIFICATIONS_META_KEY
from app.services import account_settings
from tests.conftest import (
    COACH_HOME_BASE,
    HOME_BASE,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    seed_session_summary_data,
    sync_engine,
    viewer_headers,
)


def test_get_coach_home_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_session_summary_data: dict,
) -> None:
    _ = seed_session_summary_data
    response = client.get(
        f"{COACH_HOME_BASE}?phone=%2B1-555-0100&company=Acme%20Realty",
        headers=coach_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == str(REGULAR_USER_ID)
    assert body["name"] == "Regular Coach"
    assert isinstance(body["total_sessions"], int)
    assert isinstance(body["total_players"], int)
    assert isinstance(body["recent_activities"], list)
    assert isinstance(body["attendance_records"], list)
    assert body["company"] == "Acme Realty"


def test_get_coach_home_403_without_auth(client: TestClient) -> None:
    response = client.get(COACH_HOME_BASE)
    assert response.status_code == 401


def test_get_coach_home_403_for_viewer(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.get(COACH_HOME_BASE, headers=viewer_headers)
    assert response.status_code == 403


def test_get_home_activities_200(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_session_summary_data: dict,
) -> None:
    _ = seed_session_summary_data
    response = client.get(f"{HOME_BASE}/activities", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["activities"]) <= 10
    assert body["count"] == len(body["activities"])
    assert body["limit"] == 10
    activity = body["activities"][0]
    assert {"activity_id", "activity_text", "activity_date", "user_id"} <= set(activity)


def test_get_home_activities_404_when_empty(
    client: TestClient,
    coach_headers: dict[str, str],
    ensure_practice_sessions_table: None,
) -> None:
    from sqlalchemy import text

    with sync_engine.begin() as connection:
        connection.execute(text("DELETE FROM practice_sessions"))

    response = client.get(f"{HOME_BASE}/activities", headers=coach_headers)
    assert response.status_code == 404


def test_get_home_user_info_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{HOME_BASE}/user-info", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"]
    assert body["organization_name"]
    assert body["welcome_message"]


def test_get_home_notifications_404_when_empty(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{HOME_BASE}/notifications", headers=coach_headers)
    assert response.status_code == 404


def test_get_home_notifications_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, REGULAR_USER_ID)
        assert user is not None
        meta = account_settings.get_user_meta(user)
        meta[NOTIFICATIONS_META_KEY] = [
            {
                "notification_id": "11111111-2222-3333-4444-555555555555",
                "notification_text": "Practice plan updated",
                "notification_date": datetime.now(timezone.utc).isoformat(),
            }
        ]
        account_settings.set_user_meta(user, meta)
        session.commit()

    response = client.get(f"{HOME_BASE}/notifications", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["notifications"]) == 1
    notification = body["notifications"][0]
    assert {"notification_id", "notification_text", "notification_date"} <= set(notification)


def test_home_endpoints_403_for_viewer(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    assert client.get(f"{HOME_BASE}/activities", headers=viewer_headers).status_code == 403
    assert client.get(f"{HOME_BASE}/user-info", headers=viewer_headers).status_code == 403
    assert client.get(f"{HOME_BASE}/notifications", headers=viewer_headers).status_code == 403


def test_coach_home_counts_only_active_records(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_session_summary_data: dict,
) -> None:
    from sqlalchemy import text

    _ = seed_session_summary_data
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO practice_sessions (
                    id, org_id, session_date, session_mode, recorder_user_id,
                    recorder_type, status, synced, created_at
                ) VALUES (
                    :id, :org_id, CURRENT_DATE, 'one_drill', :recorder_user_id,
                    'coach', 'deleted', true, NOW()
                )
                """
            ),
            {
                "id": "00000000-0000-4000-8000-000000000099",
                "org_id": SEEDED_ORG_ID,
                "recorder_user_id": REGULAR_USER_ID,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO players (id, org_id, first_name, last_name, player_code, active)
                VALUES (:id, :org_id, 'Inactive', 'Player', 'PC-INACTIVE', false)
                ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
                """
            ),
            {
                "id": "00000000-0000-4000-8000-000000000098",
                "org_id": SEEDED_ORG_ID,
            },
        )

    response = client.get(COACH_HOME_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_sessions"] >= 1
    assert all("description" in item and "timestamp" in item for item in body["recent_activities"])
