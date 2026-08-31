"""Cross-ticket acceptance tests for HE-455, HE-213, HE-229 player module APIs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import (
    PLAYER_DRILLS_BASE,
    PLAYER_START_BASE,
    SEEDED_PLAYER_DRILL_ONE_ID,
)
from tests.api.test_player_start import VALID_DRILLS


def test_he455_list_drills_returns_envelope_fields(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-455: authorized list response includes mobile envelope and drill details."""
    response = client.get(PLAYER_DRILLS_BASE, headers=viewer_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert "status" in body
    assert "drills" in body
    assert len(body["drills"]) >= 1
    drill = body["drills"][0]
    assert "drill_id" in drill
    assert "name" in drill
    assert "duration" in drill
    assert "status" in drill
    assert "time_remaining" in drill


def test_he455_timer_start_returns_playing_status(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-455: timer start returns playing status and time_remaining."""
    response = client.post(
        f"{PLAYER_DRILLS_BASE}/start",
        headers=viewer_headers,
        json={"drill_id": str(SEEDED_PLAYER_DRILL_ONE_ID), "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "playing"
    assert ":" in body["time_remaining"]


def test_he229_start_workout_then_drill_detail_shows_session(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-229 + HE-455: starting workout enables drill detail with session state."""
    start = client.post(
        PLAYER_START_BASE,
        headers=viewer_headers,
        json={"drills": VALID_DRILLS, "phone": "+1-555-0100"},
    )
    assert start.status_code == 201

    detail = client.get(
        f"{PLAYER_DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}",
        headers=viewer_headers,
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == str(SEEDED_PLAYER_DRILL_ONE_ID)
    assert body["name"] == "Warm-up Lap"


def test_he229_get_start_statistics_shape(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-229: GET start returns statistics block required by FE Start screen."""
    response = client.get(PLAYER_START_BASE, headers=viewer_headers)
    assert response.status_code == 200
    stats = response.json()["statistics"]
    for key in (
        "total_sessions",
        "total_attempts",
        "shooting_percentage",
        "drill_count",
        "total_duration_minutes",
    ):
        assert key in stats


def test_he229_post_start_400_unmatched_drill_names(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-229 edge case: drill names not in assigned list return 400."""
    response = client.post(
        PLAYER_START_BASE,
        headers=viewer_headers,
        json={
            "drills": [{"name": "Nonexistent Drill", "duration": 10}],
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_he455_inactive_user_cannot_access_drills(
    client: TestClient,
    inactive_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-455 auth: inactive user receives 401/403 on player drills."""
    response = client.get(PLAYER_DRILLS_BASE, headers=inactive_headers)
    assert response.status_code in {401, 403}


def test_he229_inactive_user_cannot_start_workout(
    client: TestClient,
    inactive_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-229 auth: inactive user cannot start workout."""
    response = client.post(
        PLAYER_START_BASE,
        headers=inactive_headers,
        json={"drills": VALID_DRILLS},
    )
    assert response.status_code in {401, 403}
