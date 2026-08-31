"""Integration tests for player Start screen API (HE-229)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import PLAYER_START_BASE

VALID_DRILLS = [
    {"name": "Catch & Shoot From Wing", "duration": 10},
    {"name": "Cone Slasher Layup Finishing", "duration": 8},
]


def test_get_player_start_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.get(
        f"{PLAYER_START_BASE}?phone=%2B1-555-0100",
        headers=viewer_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["status"] == "ready"
    assert "statistics" in body
    stats = body["statistics"]
    assert isinstance(stats["total_sessions"], int)
    assert isinstance(stats["total_attempts"], int)
    assert "%" in stats["shooting_percentage"]
    assert stats["drill_count"] == len(body["drills"])
    assert len(body["drills"]) == 2
    assert body["drills"][0]["name"] == "Warm-up Lap"
    assert body["drills"][0]["duration"] == 10
    assert body["workout_id"] is None


def test_start_player_workout_201(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.post(
        PLAYER_START_BASE,
        headers=viewer_headers,
        json={"drills": VALID_DRILLS, "phone": "+1-555-0100"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "started"
    assert body["message"] == "Workout started successfully"
    assert body["workout_id"]
    assert len(body["drills"]) == 2
    assert body["phone"] == "+1-555-0100"


def test_start_player_workout_400_missing_drills(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.post(
        PLAYER_START_BASE,
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_start_player_workout_400_invalid_format(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.post(
        PLAYER_START_BASE,
        headers=viewer_headers,
        json={"drills": [], "phone": "+1-555-0100"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_start_player_workout_400_blank_drill_name(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    response = client.post(
        PLAYER_START_BASE,
        headers=viewer_headers,
        json={
            "drills": [{"name": "   ", "duration": 10}],
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_start_player_workout_409_duplicate(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    first = client.post(
        PLAYER_START_BASE,
        headers=viewer_headers,
        json={"drills": VALID_DRILLS},
    )
    assert first.status_code == 201

    second = client.post(
        PLAYER_START_BASE,
        headers=viewer_headers,
        json={"drills": VALID_DRILLS},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "WORKOUT_ALREADY_ACTIVE"


def test_get_player_start_returns_active_workout_id(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    started = client.post(
        PLAYER_START_BASE,
        headers=viewer_headers,
        json={"drills": VALID_DRILLS},
    )
    assert started.status_code == 201
    workout_id = started.json()["workout_id"]

    response = client.get(PLAYER_START_BASE, headers=viewer_headers)
    assert response.status_code == 200
    assert response.json()["workout_id"] == workout_id


def test_player_start_401_unauthenticated(
    client: TestClient,
    seed_player_drills: None,
) -> None:
    response = client.get(PLAYER_START_BASE)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"
