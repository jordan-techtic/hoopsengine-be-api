"""Integration tests for coach sync activity APIs (HE-322)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import COACH_SYNC_ACTIVITY_BASE, REGULAR_USER_ID, viewer_headers


def test_get_sync_activity_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{COACH_SYNC_ACTIVITY_BASE}?phone=%2B1-555-0100",
        headers=coach_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == str(REGULAR_USER_ID)
    assert body["title"]
    assert isinstance(body["recent_activities"], list)
    assert len(body["recent_activities"]) >= 1


def test_save_sync_activity_201(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    payload = {
        "recent_activities": [
            {
                "title": "Practice Session synced successfully",
                "time": "2:34 PM",
                "status": "success",
            }
        ],
        "phone": "+1-555-0100",
    }
    response = client.post(
        f"{COACH_SYNC_ACTIVITY_BASE}/save",
        headers=coach_headers,
        json=payload,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["save_status"] == "success"
    assert body["id"] == str(REGULAR_USER_ID)
    assert body["title"] == "All Synced"
    assert body["recent_activities"][0]["title"] == payload["recent_activities"][0]["title"]


def test_save_sync_activity_400_missing_fields(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{COACH_SYNC_ACTIVITY_BASE}/save",
        headers=coach_headers,
        json={"recent_activities": []},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_save_sync_activity_400_invalid_title(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{COACH_SYNC_ACTIVITY_BASE}/save",
        headers=coach_headers,
        json={
            "recent_activities": [
                {"title": "   ", "time": "2:34 PM", "status": "success"},
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_sync_activity_403_for_viewer(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.get(COACH_SYNC_ACTIVITY_BASE, headers=viewer_headers)
    assert response.status_code == 403
