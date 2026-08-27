"""Integration tests for player statistics API (HE-313)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import SEEDED_PLAYER_JANE_ID, STATISTICS_BASE


def test_get_player_statistics_200(
    client: TestClient,
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(
        f"{STATISTICS_BASE}/{SEEDED_PLAYER_JANE_ID}",
        params={"full_name": "Jane Doe", "phone": "+1-555-0100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["id"] == str(SEEDED_PLAYER_JANE_ID)
    assert body["name"] == "Jane Doe"
    assert body["player_id"] == str(SEEDED_PLAYER_JANE_ID)
    assert "shooting_percentage" in body
    assert isinstance(body["active_field_goals"], int)
    assert isinstance(body["session_history"], list)


def test_get_player_statistics_404(
    client: TestClient,
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.get(f"{STATISTICS_BASE}/00000000-0000-4000-8000-000000000099")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PLAYER_NOT_FOUND"


def test_get_player_statistics_400_invalid_id(client: TestClient) -> None:
    response = client.get(f"{STATISTICS_BASE}/not-a-uuid")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
