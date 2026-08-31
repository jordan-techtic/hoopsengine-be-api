"""Integration tests for organization admin custom UI design API (HE-453)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import (
    CUSTOM_UI_DESIGN_BASE,
    CUSTOM_UI_DESIGNS_BASE,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    UI_DESIGN_FEEDBACK_BASE,
    UI_DESIGN_SAVE_BASE,
    UI_DESIGN_TEMPLATES_BASE,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000053")

VALID_DESIGN_PAYLOAD = {
    "template_name": "Custom Design Template",
    "elements": [
        {
            "type": "text",
            "content": "Sample Text",
            "text_color": "#1A1A1A",
            "background_color": "#FFFFFF",
        }
    ],
    "approved": True,
}

VALID_FEEDBACK_PAYLOAD = {
    "feedback": "The layout is intuitive and easy to navigate.",
    "rating": 5,
}


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        existing = session.get(User, ORG_ADMIN_ID)
        if existing is None:
            org_admin = User(
                id=ORG_ADMIN_ID,
                email="orgadmin.customui@test.com",
                username="orgadmincustomui",
                encrypted_password=hash_password("OrgAdmin123!"),
                role=UserRole.ORG_ADMIN.value,
                first_name="Org",
                last_name="Admin",
                is_super_admin=False,
                is_active=True,
                org_id=SEEDED_ORG_ID,
                email_confirmed_at=datetime.now(timezone.utc),
            )
            session.add(org_admin)
            session.commit()
    return auth_headers(create_access_token(ORG_ADMIN_ID))


@pytest.fixture
def coach_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for a coach user (non org-admin)."""
    return auth_headers(create_access_token(REGULAR_USER_ID))


def test_save_custom_design_201(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.post(
        CUSTOM_UI_DESIGN_BASE,
        json=VALID_DESIGN_PAYLOAD,
        headers=org_admin_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Custom design saved successfully."
    assert body["data"]["template_name"] == VALID_DESIGN_PAYLOAD["template_name"]
    assert body["data"]["elements"][0]["content"] == "Sample Text"


def test_save_missing_template_name_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(VALID_DESIGN_PAYLOAD)
    payload["template_name"] = ""
    response = client.post(CUSTOM_UI_DESIGN_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_save_missing_elements_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(VALID_DESIGN_PAYLOAD)
    payload["elements"] = []
    response = client.post(CUSTOM_UI_DESIGN_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 422


def test_save_without_approval_409(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(VALID_DESIGN_PAYLOAD)
    payload["approved"] = False
    response = client.post(CUSTOM_UI_DESIGN_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "APPROVAL_REQUIRED"


def test_save_invalid_contrast_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    payload = dict(VALID_DESIGN_PAYLOAD)
    payload["elements"] = [
        {
            "type": "text",
            "content": "Low contrast text",
            "text_color": "#CCCCCC",
            "background_color": "#FFFFFF",
        }
    ]
    response = client.post(CUSTOM_UI_DESIGN_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_designs_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    client.post(CUSTOM_UI_DESIGN_BASE, json=VALID_DESIGN_PAYLOAD, headers=org_admin_headers)
    response = client.get(CUSTOM_UI_DESIGNS_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) >= 1
    assert body["data"][0]["template_name"] == VALID_DESIGN_PAYLOAD["template_name"]


def test_get_designs_404_no_templates(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    with Session(sync_engine) as session:
        session.execute(
            text("DELETE FROM org_ui_designs_staging WHERE org_id = :org_id"),
            {"org_id": str(SEEDED_ORG_ID)},
        )
        session.commit()
    response = client.get(CUSTOM_UI_DESIGNS_BASE, headers=org_admin_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DESIGNS_NOT_FOUND"


def test_ui_design_save_alias_201(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.post(
        UI_DESIGN_SAVE_BASE,
        json=VALID_DESIGN_PAYLOAD,
        headers=org_admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["message"] == "Custom design saved successfully."


def test_ui_design_templates_alias_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    client.post(UI_DESIGN_SAVE_BASE, json=VALID_DESIGN_PAYLOAD, headers=org_admin_headers)
    response = client.get(UI_DESIGN_TEMPLATES_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_submit_feedback_201(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    save_response = client.post(
        CUSTOM_UI_DESIGN_BASE,
        json=VALID_DESIGN_PAYLOAD,
        headers=org_admin_headers,
    )
    design_id = save_response.json()["data"]["id"]
    payload = dict(VALID_FEEDBACK_PAYLOAD)
    payload["design_id"] = design_id

    response = client.post(UI_DESIGN_FEEDBACK_BASE, json=payload, headers=org_admin_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Feedback submitted successfully."
    assert body["data"]["design_id"] == design_id
    assert body["data"]["status"] == "submitted"


def test_submit_feedback_duplicate_409(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    client.post(UI_DESIGN_FEEDBACK_BASE, json=VALID_FEEDBACK_PAYLOAD, headers=org_admin_headers)
    response = client.post(UI_DESIGN_FEEDBACK_BASE, json=VALID_FEEDBACK_PAYLOAD, headers=org_admin_headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FEEDBACK_LIMIT_REACHED"


def test_custom_ui_forbidden_coach_403(
    coach_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.get(CUSTOM_UI_DESIGNS_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
