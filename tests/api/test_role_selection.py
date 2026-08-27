"""Integration tests for role selection API (HE-294)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ROLE_SELECTION_BASE = "/api/v1/role-selection"


def _submit_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "selected_role": "Coach",
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_submit_valid_coach_role_201(client: TestClient) -> None:
    response = client.post(ROLE_SELECTION_BASE, json=_submit_payload(selected_role="Coach"))
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["selected_role"] == "coach"
    assert body["role"] == "coach"
    assert body["session_token"]
    assert body["link"]
    assert body["title"] == "Select Your Role"


@pytest.mark.parametrize("role_label", ["Coach", "Player", "Organiser"])
def test_submit_valid_roles_201(client: TestClient, role_label: str) -> None:
    response = client.post(ROLE_SELECTION_BASE, json=_submit_payload(selected_role=role_label))
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["selected_role"] in {"coach", "player", "org_admin"}


def test_submit_empty_role_400(client: TestClient) -> None:
    response = client.post(ROLE_SELECTION_BASE, json=_submit_payload(selected_role="   "))
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "selected_role"


def test_submit_referee_role_400(client: TestClient) -> None:
    response = client.post(ROLE_SELECTION_BASE, json=_submit_payload(selected_role="Referee"))
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_submit_invalid_role_not_listed_409(client: TestClient) -> None:
    response = client.post(ROLE_SELECTION_BASE, json=_submit_payload(selected_role="Super Admin"))
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "ROLE_NOT_ALLOWED"


def test_resubmit_unchanged_role_409(client: TestClient) -> None:
    first = client.post(ROLE_SELECTION_BASE, json=_submit_payload(selected_role="Coach"))
    assert first.status_code == 201
    session_token = first.json()["session_token"]

    second = client.post(
        ROLE_SELECTION_BASE,
        json=_submit_payload(selected_role="Coach", session_token=session_token),
    )
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "ROLE_SELECTION_UNCHANGED"


def test_get_roles_catalog_200(client: TestClient) -> None:
    response = client.get(f"{ROLE_SELECTION_BASE}/roles")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["title"] == "Select Your Role"
    assert len(body["roles"]) == 3
    labels = {item["label"] for item in body["roles"]}
    assert labels == {"Coach", "Player", "Organiser"}


def test_get_current_selection_200(client: TestClient) -> None:
    created = client.post(ROLE_SELECTION_BASE, json=_submit_payload(selected_role="Player"))
    assert created.status_code == 201
    session_token = created.json()["session_token"]

    response = client.get(ROLE_SELECTION_BASE, params={"session_token": session_token})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["selected_role"] == "player"
    assert body["role"] == "player"
    assert body["session_token"] == session_token


def test_role_persisted_in_database(client: TestClient) -> None:
    response = client.post(ROLE_SELECTION_BASE, json=_submit_payload(selected_role="Organiser"))
    assert response.status_code == 201
    session_token = response.json()["session_token"]

    get_response = client.get(ROLE_SELECTION_BASE, params={"session_token": session_token})
    assert get_response.status_code == 200
    assert get_response.json()["selected_role"] == "org_admin"
