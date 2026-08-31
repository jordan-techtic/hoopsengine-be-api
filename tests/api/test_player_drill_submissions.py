"""Integration tests for player drill submission API (HE-226)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import PLAYER_DRILL_SUBMISSIONS_BASE, sync_engine


@pytest.fixture(autouse=True)
def _drill_submissions_table(ensure_practice_plans_table: None) -> None:
    """Ensure drill_submissions table exists for player drill submission tests."""
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.drill_submissions (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    org_id uuid REFERENCES public.organizations(id),
                    submitted_by uuid,
                    submitted_by_player_id uuid,
                    drill_name text NOT NULL,
                    category text,
                    description text,
                    directions text,
                    keys text,
                    status text DEFAULT 'pending',
                    submitted_at timestamptz DEFAULT now()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                ALTER TABLE public.drill_submissions
                ADD COLUMN IF NOT EXISTS submitted_by_player_id uuid
                """
            )
        )
        connection.execute(text("DELETE FROM drill_submissions"))


def _submit_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "drill_name": "Player Fast Break Drill",
        "category": "Shooting",
        "difficulty_level": "Intermediate",
        "description": "Outline the setup, rotation rules, and primary coaching cues.",
        "full_name": "Player Fast Break Drill",
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_submit_player_drill_submission_201(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.post(
        PLAYER_DRILL_SUBMISSIONS_BASE,
        headers=viewer_headers,
        json=_submit_payload(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["name"] == "Player Fast Break Drill"
    assert body["category"] == "Shooting"
    assert body["difficulty_level"] == "Intermediate"
    assert body["id"]
    assert body["message"]
    assert body["status"] == "submitted"


def test_submit_player_drill_submission_400_missing_drill_name(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.post(
        PLAYER_DRILL_SUBMISSIONS_BASE,
        headers=viewer_headers,
        json=_submit_payload(drill_name="", full_name=""),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_submit_player_drill_submission_409_duplicate_name(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    first = client.post(
        PLAYER_DRILL_SUBMISSIONS_BASE,
        headers=viewer_headers,
        json=_submit_payload(),
    )
    assert first.status_code == 201

    second = client.post(
        PLAYER_DRILL_SUBMISSIONS_BASE,
        headers=viewer_headers,
        json=_submit_payload(),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DRILL_IDEA_ALREADY_EXISTS"


def test_submit_player_drill_submission_400_missing_required_fields(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.post(
        PLAYER_DRILL_SUBMISSIONS_BASE,
        headers=viewer_headers,
        json={
            "drill_name": "Missing Fields Drill",
            "category": "",
            "difficulty_level": "Intermediate",
            "description": "",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_submit_player_drill_submission_400_invalid_difficulty(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    response = client.post(
        PLAYER_DRILL_SUBMISSIONS_BASE,
        headers=viewer_headers,
        json=_submit_payload(difficulty_level="Expert"),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "difficulty_level"


def test_list_player_drill_submissions_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    created = client.post(
        PLAYER_DRILL_SUBMISSIONS_BASE,
        headers=viewer_headers,
        json=_submit_payload(drill_name="Listed Player Drill", full_name="Listed Player Drill"),
    )
    assert created.status_code == 201
    submission_id = created.json()["id"]

    response = client.get(PLAYER_DRILL_SUBMISSIONS_BASE, headers=viewer_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert len(body["drill_submissions"]) >= 1
    item = next(row for row in body["drill_submissions"] if row["id"] == submission_id)
    assert item["name"] == "Listed Player Drill"
    assert item["category"] == "Shooting"
    assert item["difficulty_level"] == "Intermediate"
    assert item["description"]
    assert item["status"] == "pending"


def test_get_player_drill_submission_200(
    client: TestClient,
    viewer_headers: dict[str, str],
    seed_leaderboard_data: dict,
) -> None:
    _ = seed_leaderboard_data
    created = client.post(
        PLAYER_DRILL_SUBMISSIONS_BASE,
        headers=viewer_headers,
        json=_submit_payload(drill_name="Detail Player Drill", full_name="Detail Player Drill"),
    )
    assert created.status_code == 201
    submission_id = created.json()["id"]

    response = client.get(
        f"{PLAYER_DRILL_SUBMISSIONS_BASE}/{submission_id}",
        headers=viewer_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["id"] == submission_id
    assert body["name"] == "Detail Player Drill"
    assert body["category"] == "Shooting"
    assert body["difficulty_level"] == "Intermediate"
    assert body["description"]
