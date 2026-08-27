"""Integration tests for drill search API (HE-309)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import DRILLS_SEARCH_BASE


@pytest.fixture(autouse=True)
def _practice_plan_tables(ensure_practice_plans_table: None) -> None:
    """Ensure drills table is seeded for search tests."""


def test_search_drills_200_matching_results(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_SEARCH_BASE}?q=throw", headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    names = [drill["name"] for drill in body["drills"]]
    assert "Free Throw Line" in names
    assert "Free Throw Set" in names
    assert all("throw" in name.lower() for name in names)


def test_search_drills_200_warmup(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_SEARCH_BASE}?q=Warm", headers=coach_headers)
    assert response.status_code == 200
    names = [drill["name"] for drill in response.json()["drills"]]
    assert "Warm-up Lap" in names


def test_search_drills_400_empty_query(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_SEARCH_BASE}?q=", headers=coach_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_search_drills_400_missing_query(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(DRILLS_SEARCH_BASE, headers=coach_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_search_drills_403_for_viewer(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.get(f"{DRILLS_SEARCH_BASE}?q=warm", headers=viewer_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
