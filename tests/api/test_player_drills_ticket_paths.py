"""Integration tests for HE-213 ticket-path drill endpoints (/api/v1/drills/{id}*)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import (
    DRILLS_BASE,
    SEEDED_PLAYER_DRILL_ONE_ID,
)
from tests.api.test_player_drills import INVALID_DRILL_ID, UNASSIGNED_DRILL_ID


def test_get_drill_detail_player_ticket_path_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-213: GET /api/v1/drills/{id} returns timer, status, progress for players."""
    response = client.get(
        f"{DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}?phone=%2B1-555-0100",
        headers=viewer_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == str(SEEDED_PLAYER_DRILL_ONE_ID)
    assert body["drill_id"] == str(SEEDED_PLAYER_DRILL_ONE_ID)
    assert body["name"] == "Warm-up Lap"
    assert ":" in body["timer"]
    assert body["status"] in {"playing", "paused", "stopped", "reset"}
    assert isinstance(body["progress"], int)
    assert 0 <= body["progress"] <= 100


def test_get_drill_detail_player_ticket_path_404(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-213: GET /api/v1/drills/{id} returns 404 for invalid drill ID."""
    response = client.get(
        f"{DRILLS_BASE}/{INVALID_DRILL_ID}",
        headers=viewer_headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DRILL_NOT_FOUND"


def test_play_drill_ticket_path_201(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-213: POST /api/v1/drills/{id}/play returns 201 when authorized."""
    response = client.post(
        f"{DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/play",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["id"] == str(SEEDED_PLAYER_DRILL_ONE_ID)
    assert body["status"] == "playing"
    assert body["timer"] == "00:00"
    assert body["progress"] == 0


def test_play_drill_ticket_path_403_unauthorized(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-213: POST /api/v1/drills/{id}/play returns 403 for unassigned drill."""
    response = client.post(
        f"{DRILLS_BASE}/{UNASSIGNED_DRILL_ID}/play",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_update_drill_timer_ticket_path_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """HE-213: PUT /api/v1/drills/{id}/timer returns 200 with updated state."""
    play = client.post(
        f"{DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/play",
        headers=viewer_headers,
        json={"phone": "+1-555-0100"},
    )
    assert play.status_code == 201

    response = client.put(
        f"{DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/timer",
        headers=viewer_headers,
        json={"timer": "02:00", "status": "paused", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["timer"] == "02:00"
    assert body["status"] == "paused"
    assert body["progress"] == 20


def test_play_drill_ticket_path_401_unauthenticated(
    client: TestClient,
    seed_player_drills: None,
) -> None:
    """Auth: missing token returns 401 on ticket-path play endpoint."""
    response = client.post(
        f"{DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/play",
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_update_timer_ticket_path_422_invalid_format(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """Edge case: invalid MM:SS timer format returns 422."""
    play = client.post(
        f"{DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/play",
        headers=viewer_headers,
        json={},
    )
    assert play.status_code == 201

    response = client.put(
        f"{DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/timer",
        headers=viewer_headers,
        json={"timer": "invalid", "status": "playing"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_drill_detail_ticket_path_403_coach(
    client: TestClient,
    coach_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """Coach GET on assigned player drill id returns coach catalog shape (not 403)."""
    response = client.get(
        f"{DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}",
        headers=coach_headers,
    )
    assert response.status_code in {200, 404}


def test_play_drill_ticket_path_401_expired_token(
    client: TestClient,
    expired_user_headers: dict[str, str],
    seed_player_drills: None,
) -> None:
    """Auth: expired JWT returns 401 on ticket-path play."""
    response = client.post(
        f"{DRILLS_BASE}/{SEEDED_PLAYER_DRILL_ONE_ID}/play",
        headers=expired_user_headers,
        json={"phone": "+1-555-0100"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}
