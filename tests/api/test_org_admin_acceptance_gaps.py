"""Cross-cutting org-admin acceptance tests (auth, edge cases, AC gaps)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import (
    ANALYTICS_BASE,
    BILLING_HISTORY_BASE,
    CUSTOM_UI_DESIGN_BASE,
    INACTIVE_ID,
    ORG_ADMIN_LOGIN_BASE,
    ORGANIZATION_PROFILE_BASE,
    REPORTS_BASE,
    SEEDED_ORG_ID,
    TEST_VALID_PASSWORD,
    VIEWER_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_GAP_ID = UUID("00000000-0000-4000-8000-000000000057")
VALID_REPORT_CRITERIA = {"criteria": {"date_range": "2020-01-01 to 2030-12-31"}}


@pytest.fixture
def org_admin_gap_headers(seeded_users: dict) -> dict[str, str]:
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_GAP_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_GAP_ID,
                    email="orgadmin.gap@test.com",
                    username="orgadmingap",
                    encrypted_password=hash_password(TEST_VALID_PASSWORD),
                    role=UserRole.ORG_ADMIN.value,
                    first_name="Gap",
                    last_name="Admin",
                    is_super_admin=False,
                    is_active=True,
                    org_id=SEEDED_ORG_ID,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
    return auth_headers(create_access_token(ORG_ADMIN_GAP_ID))


@pytest.fixture
def viewer_headers(seeded_users: dict) -> dict[str, str]:
    return auth_headers(create_access_token(VIEWER_ID))


@pytest.fixture
def inactive_headers(seeded_users: dict) -> dict[str, str]:
    return auth_headers(create_access_token(INACTIVE_ID))


def test_org_admin_endpoints_reject_viewer_403(
    viewer_headers: dict[str, str], client: TestClient
) -> None:
    assert client.get(ORGANIZATION_PROFILE_BASE, headers=viewer_headers).status_code == 403
    assert client.get(BILLING_HISTORY_BASE, headers=viewer_headers).status_code == 403


def test_org_admin_endpoints_reject_inactive_user_401(
    inactive_headers: dict[str, str], client: TestClient
) -> None:
    assert client.get(BILLING_HISTORY_BASE, headers=inactive_headers).status_code == 401


def test_report_export_csv_decodes_to_metrics(
    org_admin_gap_headers: dict[str, str], client: TestClient
) -> None:
    created = client.post(
        f"{REPORTS_BASE}/generate", json=VALID_REPORT_CRITERIA, headers=org_admin_gap_headers
    )
    report_id = created.json()["report_id"]
    exported = client.post(
        f"{REPORTS_BASE}/export",
        json={"report_id": report_id, "format": "csv"},
        headers=org_admin_gap_headers,
    )
    assert exported.status_code == 200
    decoded = base64.b64decode(exported.json()["content_base64"]).decode("utf-8")
    assert "total_sessions" in decoded


def test_analytics_filter_unicode_date_range_edge_case(
    org_admin_gap_headers: dict[str, str], client: TestClient
) -> None:
    response = client.post(
        f"{ANALYTICS_BASE}/filter",
        json={"filters": {"date_range": "2020-01-01\u2003to\u20032030-12-31"}},
        headers=org_admin_gap_headers,
    )
    assert response.status_code == 400


def test_custom_ui_save_missing_auth_401(client: TestClient) -> None:
    response = client.post(
        CUSTOM_UI_DESIGN_BASE,
        json={"template_name": "T", "elements": [{"type": "text", "content": "x"}], "approved": True},
    )
    assert response.status_code == 401


def test_org_admin_login_by_email_username_edge_case(
    client: TestClient, org_admin_gap_headers: dict[str, str]
) -> None:
    with Session(sync_engine) as session:
        user = session.get(User, ORG_ADMIN_GAP_ID)
        assert user is not None
        response = client.post(
            ORG_ADMIN_LOGIN_BASE,
            json={"email": user.email, "username": user.email, "password": TEST_VALID_PASSWORD},
        )
    assert response.status_code == 200
    assert response.json()["access_token"]
