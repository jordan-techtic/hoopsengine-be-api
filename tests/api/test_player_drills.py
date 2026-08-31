"""Integration tests for player Active Drill API (HE-455, HE-213)."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from tests.conftest import (
    PLAYER_DRILLS_BASE,
    SEEDED_PLAYER_DRILL_ONE_ID,
    SEEDED_PLAYER_DRILL_TWO_ID,
)

INVALID_DRILL_ID = "00000000-0000-4000-8000-000000000099"
UNASSIGNED_DRILL_ID = "00000000-0000-4000-8000-000000000044"


def test_list_player_drills_200_authorized(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.get(
        f"{PLAYER_DRILLS_BASE}?phone=%2B1-555-0100",
        headers=viewer_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert len(body["drills"]) == 2
    drill_ids = {item["drill_id"] for item in body["drills"]}
    assert str(SEEDED_PLAYER_DRILL_ONE_ID) in drill_ids
    assert str(SEEDED_PLAYER_DRILL_TWO_ID) in drill_ids
    for item in body["drills"]:
        assert item["status"] in {"playing", "stopped", "reset"}
        assert ":" in item["time_remaining"]


def test_list_player_drills_only_active_subteam_drills(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.get(PLAYER_DRILLS_BASE, headers=viewer_headers)
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["drills"]}
    assert "Warm-up Lap" in names
    assert "3-Point Corner" in names
    assert "Inactive Spot Up" not in names


def test_start_player_drill_timer_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.post(
        f"{PLAYER_DRILLS_BASE}/start",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "playing"
    assert body["time_remaining"]
    assert body["drill_id"] == str(SEEDED_PLAYER_DRILL_ONE_ID)


def test_reset_player_drill_timer_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    start = client.post(
        f"{PLAYER_DRILLS_BASE}/start",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert start.status_code == 200
    response = client.post(
        f"{PLAYER_DRILLS_BASE}/reset",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "reset"
    assert body["time_remaining"] == "10:00"


def test_stop_player_drill_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    start = client.post(
        f"{PLAYER_DRILLS_BASE}/start",
        headers=viewer_headers,
        json={"drill_id": str(SEEDED_PLAYER_DRILL_ONE_ID)},
    )
    assert start.status_code == 200
    response = client.post(
        f"{PLAYER_DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/stop",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "stopped"


def test_get_player_drill_detail_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.get(
        f"{PLAYER_DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}",
        headers=viewer_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["drill_id"] == str(SEEDED_PLAYER_DRILL_ONE_ID)
    assert body["id"] == str(SEEDED_PLAYER_DRILL_ONE_ID)
    assert body["name"] == "Warm-up Lap"
    assert body["duration"] == 600
    assert body["status"] in {"playing", "paused", "stopped", "reset"}
    assert ":" in body["timer"]
    assert isinstance(body["progress"], int)
    assert 0 <= body["progress"] <= 100


def test_get_player_drill_detail_404_invalid_id(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.get(
        f"{PLAYER_DRILLS_BASE}/{INVALID_DRILL_ID}",
        headers=viewer_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DRILL_NOT_FOUND"


def test_player_drills_403_coach_forbidden(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.get(PLAYER_DRILLS_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_player_drills_401_unauthenticated(
    client: TestClient,
    seed_player_drills: None,
) -> None:
    response = client.get(PLAYER_DRILLS_BASE)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_start_stop_reset_timer_flow(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    start = client.post(
        f"{PLAYER_DRILLS_BASE}/start",
        headers=viewer_headers,
        json={"drill_id": str(SEEDED_PLAYER_DRILL_ONE_ID)},
    )
    assert start.status_code == 200
    assert start.json()["status"] == "playing"

    stop = client.post(
        f"{PLAYER_DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/stop",
        headers=viewer_headers,
        json={},
    )
    assert stop.status_code == 200
    assert stop.json()["status"] == "stopped"

    reset = client.post(
        f"{PLAYER_DRILLS_BASE}/reset",
        headers=viewer_headers,
        json={"drill_id": str(SEEDED_PLAYER_DRILL_ONE_ID)},
    )
    assert reset.status_code == 200
    assert reset.json()["status"] == "reset"


def test_reset_player_drill_400_without_workout(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.post(
        f"{PLAYER_DRILLS_BASE}/reset",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_stop_player_drill_400_wrong_active_drill(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    start = client.post(
        f"{PLAYER_DRILLS_BASE}/start",
        headers=viewer_headers,
        json={"drill_id": str(SEEDED_PLAYER_DRILL_ONE_ID)},
    )
    assert start.status_code == 200
    response = client.post(
        f"{PLAYER_DRILLS_BASE}/{SEEDED_PLAYER_DRILL_TWO_ID}/stop",
        headers=viewer_headers,
        json={},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_play_player_drill_201(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.post(
        f"{PLAYER_DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/play",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["id"] == str(SEEDED_PLAYER_DRILL_ONE_ID)
    assert body["name"] == "Warm-up Lap"
    assert body["status"] == "playing"
    assert body["timer"] == "00:00"
    assert body["progress"] == 0
    assert body["phone"] == "+1-555-0100"


def test_play_player_drill_403_unauthorized(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.post(
        f"{PLAYER_DRILLS_BASE}/{UNASSIGNED_DRILL_ID}/play",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_update_player_drill_timer_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    play = client.post(
        f"{PLAYER_DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/play",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert play.status_code == 201

    response = client.put(
        f"{PLAYER_DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/timer",
        headers=viewer_headers,
        json={"timer": "01:30", "status": "paused", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == str(SEEDED_PLAYER_DRILL_ONE_ID)
    assert body["timer"] == "01:30"
    assert body["status"] == "paused"
    assert body["progress"] == 15
