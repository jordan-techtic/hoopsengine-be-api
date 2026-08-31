"""Integration tests for player invitation code verification (HE-212)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import (
    PLAYER_INVITATION_CODE,
    PLAYER_VERIFY_CODE_BASE,
    REDEEMED_PLAYER_INVITATION_CODE,
    SEEDED_INVITATION_PLAYER_ID,
    SEEDED_ORG_ID,
)


def _invitation_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "invitation_code": PLAYER_INVITATION_CODE,
        "phone": "+1-555-0100",
    }
    payload.update(overrides)
    return payload


def test_verify_valid_invitation_code_201(
    client: TestClient,
    seed_player_invitation_players: None,
) -> None:
    response = client.post(PLAYER_VERIFY_CODE_BASE, json=_invitation_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["title"] == "Player Code Verification"
    assert body["message"] == "Invitation code verified successfully"
    assert body["status"] == "verified"
    assert body["organization"] == "Seeded Hoops Club"
    assert body["code"] == PLAYER_INVITATION_CODE
    assert body["verification_code"] == PLAYER_INVITATION_CODE
    assert body["player_code"] == PLAYER_INVITATION_CODE
    assert body["id"] == str(SEEDED_INVITATION_PLAYER_ID)
    assert body["player_id"] == str(SEEDED_INVITATION_PLAYER_ID)
    assert body["org_id"] == str(SEEDED_ORG_ID)
    assert body["error"] is None
    assert body["link"]


def test_verify_empty_invitation_code_400(
    client: TestClient,
    seed_player_invitation_players: None,
) -> None:
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_invitation_payload(invitation_code="   "),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "invitation_code"


def test_verify_invalid_format_400(
    client: TestClient,
    seed_player_invitation_players: None,
) -> None:
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_invitation_payload(invitation_code="PLAY-7492"),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "invitation_code"


def test_verify_unknown_code_404(
    client: TestClient,
    seed_player_invitation_players: None,
) -> None:
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_invitation_payload(invitation_code="PC-00000000"),
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "INVITATION_CODE_NOT_FOUND"


def test_verify_case_sensitive_400(
    client: TestClient,
    seed_player_invitation_players: None,
) -> None:
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_invitation_payload(invitation_code=PLAYER_INVITATION_CODE.lower()),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "invitation_code"


def test_verify_already_redeemed_code_409(
    client: TestClient,
    seed_player_invitation_players: None,
) -> None:
    response = client.post(
        PLAYER_VERIFY_CODE_BASE,
        json=_invitation_payload(invitation_code=REDEEMED_PLAYER_INVITATION_CODE),
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "INVITATION_ALREADY_REDEEMED"
