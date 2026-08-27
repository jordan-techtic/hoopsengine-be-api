"""Integration tests for coach drill idea submission API (HE-321)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import DRILL_IDEAS_BASE, sync_engine


@pytest.fixture(autouse=True)
def _drill_submissions_table(ensure_practice_plans_table: None) -> None:
    """Ensure drill_submissions table exists for drill idea tests."""
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.drill_submissions (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    org_id uuid REFERENCES public.organizations(id),
                    submitted_by uuid,
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
        connection.execute(text("DELETE FROM drill_submissions"))


def _submit_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "drill_name": "3-on-2 Fast Break Transition",
        "category": "Shooting",
        "difficulty_level": "Intermediate",
        "instructions": "Outline the setup, rotation rules, and primary coaching cues.",
        "full_name": "3-on-2 Fast Break Transition",
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_submit_drill_idea_201(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(DRILL_IDEAS_BASE, headers=coach_headers, json=_submit_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["name"] == "3-on-2 Fast Break Transition"
    assert body["category"] == "Shooting"
    assert body["difficulty_level"] == "Intermediate"
    assert body["instructions"]
    assert body["id"]
    assert body["message"]
    assert body["status"] == "submitted"


def test_submit_drill_idea_400_missing_drill_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        DRILL_IDEAS_BASE,
        headers=coach_headers,
        json=_submit_payload(drill_name="", full_name=""),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_submit_drill_idea_400_invalid_difficulty(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        DRILL_IDEAS_BASE,
        headers=coach_headers,
        json=_submit_payload(difficulty_level="Expert"),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "difficulty_level"


def test_submit_drill_idea_400_empty_instructions(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        DRILL_IDEAS_BASE,
        headers=coach_headers,
        json=_submit_payload(instructions="   "),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_submit_drill_idea_409_duplicate_name_in_submissions(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    first = client.post(DRILL_IDEAS_BASE, headers=coach_headers, json=_submit_payload())
    assert first.status_code == 201

    second = client.post(DRILL_IDEAS_BASE, headers=coach_headers, json=_submit_payload())
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "DRILL_IDEA_ALREADY_EXISTS"


def test_submit_drill_idea_409_existing_catalog_drill_name(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        DRILL_IDEAS_BASE,
        headers=coach_headers,
        json=_submit_payload(drill_name="Spot Up", full_name="Spot Up"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DRILL_IDEA_ALREADY_EXISTS"


def test_list_drill_ideas_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    created = client.post(DRILL_IDEAS_BASE, headers=coach_headers, json=_submit_payload())
    assert created.status_code == 201

    response = client.get(DRILL_IDEAS_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert len(body["drill_ideas"]) >= 1
    item = body["drill_ideas"][0]
    assert item["name"] == "3-on-2 Fast Break Transition"
    assert item["category"] == "Shooting"
    assert item["difficulty_level"] == "Intermediate"
    assert item["status"] == "pending"


def test_list_drill_ideas_200_empty(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(DRILL_IDEAS_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["drill_ideas"] == []


def test_submit_drill_idea_403_viewer(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(DRILL_IDEAS_BASE, headers=viewer_headers, json=_submit_payload())
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_submit_drill_idea_201_full_name_alias(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        DRILL_IDEAS_BASE,
        headers=coach_headers,
        json={
            "category": "Shooting",
            "difficulty_level": "Beginner",
            "instructions": "Use the full_name alias for drill name.",
            "full_name": "Custom Full Name Drill",
            "phone": "+1-555-0100",
        },
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Custom Full Name Drill"
