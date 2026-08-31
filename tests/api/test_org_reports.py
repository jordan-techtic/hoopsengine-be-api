"""Integration tests for organization admin reports API (HE-449)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import (
    REGULAR_USER_ID,
    REPORTS_BASE,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000050")
VALID_CRITERIA = {
    "criteria": {
        "date_range": "2020-01-01 to 2030-12-31",
        "user_segments": ["segment1", "segment2"],
    }
}


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        existing = session.get(User, ORG_ADMIN_ID)
        if existing is None:
            org_admin = User(
                id=ORG_ADMIN_ID,
                email="orgadmin.reports@test.com",
                username="orgadminreports",
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


def test_generate_report_201(org_admin_headers: dict[str, str], client: TestClient) -> None:
    response = client.post(f"{REPORTS_BASE}/generate", json=VALID_CRITERIA, headers=org_admin_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["report_id"]
    assert body["message"]
    assert "total_coaches" in body["data"]
    assert body["error"] is None


def test_generate_invalid_criteria_400(org_admin_headers: dict[str, str], client: TestClient) -> None:
    response = client.post(
        f"{REPORTS_BASE}/generate",
        json={"criteria": {"date_range": "bad-range"}},
        headers=org_admin_headers,
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_get_report_200(org_admin_headers: dict[str, str], client: TestClient) -> None:
    created = client.post(f"{REPORTS_BASE}/generate", json=VALID_CRITERIA, headers=org_admin_headers)
    assert created.status_code == 201
    report_id = created.json()["report_id"]

    response = client.get(f"{REPORTS_BASE}/{report_id}", headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["report_id"] == report_id
    assert body["data"]["total_sessions"] >= 0
    assert body["generated_at"]


def test_get_report_404(org_admin_headers: dict[str, str], client: TestClient) -> None:
    missing_id = uuid4()
    response = client.get(f"{REPORTS_BASE}/{missing_id}", headers=org_admin_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REPORT_NOT_FOUND"


def test_export_report_csv_200(org_admin_headers: dict[str, str], client: TestClient) -> None:
    created = client.post(f"{REPORTS_BASE}/generate", json=VALID_CRITERIA, headers=org_admin_headers)
    report_id = created.json()["report_id"]

    response = client.post(
        f"{REPORTS_BASE}/export",
        json={"report_id": report_id, "format": "csv"},
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Report exported successfully."
    assert body["format"] == "csv"
    assert body["content_base64"]
    assert body["filename"].endswith(".csv")


def test_export_report_pdf_200(org_admin_headers: dict[str, str], client: TestClient) -> None:
    created = client.post(f"{REPORTS_BASE}/generate", json=VALID_CRITERIA, headers=org_admin_headers)
    report_id = created.json()["report_id"]

    response = client.post(
        f"{REPORTS_BASE}/export",
        json={"report_id": report_id, "format": "pdf"},
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "pdf"
    assert body["filename"].endswith(".pdf")


def test_reports_forbidden_for_coach_403(coach_headers: dict[str, str], client: TestClient) -> None:
    response = client.post(f"{REPORTS_BASE}/generate", json=VALID_CRITERIA, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_generate_empty_criteria_message(org_admin_headers: dict[str, str], client: TestClient) -> None:
    """Far-future narrow window may yield empty metrics with appropriate message."""
    response = client.post(
        f"{REPORTS_BASE}/generate",
        json={"criteria": {"date_range": "2099-01-01 to 2099-01-02"}},
        headers=org_admin_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["message"]
    assert body["data"]["total_sessions"] == 0
