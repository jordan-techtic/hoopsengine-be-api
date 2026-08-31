"""Integration tests for organization admin analytics API (HE-452)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from unittest.mock import patch

import jwt
from datetime import timedelta

from app.core.config import settings
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.user import User
from tests.conftest import (
    ANALYTICS_BASE,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000052")
EMPTY_ORG_ID = UUID("00000000-0000-4000-8000-000000000053")
EMPTY_ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000054")

VALID_FILTERS = {
    "filters": {
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
                email="orgadmin.analytics@test.com",
                username="orgadminanalytics",
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
def empty_org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Org admin linked to an organization with no coaches, players, or sessions."""
    with Session(sync_engine) as session:
        if session.get(Organization, EMPTY_ORG_ID) is None:
            session.add(
                Organization(
                    id=EMPTY_ORG_ID,
                    name="Empty Analytics Org",
                    admin_email="empty.analytics@test.com",
                    phone_number="5550001111",
                    address="0 Empty St",
                    join_code="EMPTYORG",
                )
            )
        existing = session.get(User, EMPTY_ORG_ADMIN_ID)
        if existing is None:
            session.add(
                User(
                    id=EMPTY_ORG_ADMIN_ID,
                    email="empty.orgadmin.analytics@test.com",
                    username="emptyorgadmin",
                    encrypted_password=hash_password("OrgAdmin123!"),
                    role=UserRole.ORG_ADMIN.value,
                    first_name="Empty",
                    last_name="Admin",
                    is_super_admin=False,
                    is_active=True,
                    org_id=EMPTY_ORG_ID,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
        session.commit()
    return auth_headers(create_access_token(EMPTY_ORG_ADMIN_ID))


@pytest.fixture
def coach_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for a coach user (non org-admin)."""
    return auth_headers(create_access_token(REGULAR_USER_ID))


def test_get_analytics_dashboard_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.get(ANALYTICS_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Analytics dashboard loaded successfully."
    assert body["data"]["total_coaches"] >= 0
    assert body["insights"]
    assert body["error"] is None


def test_get_analytics_no_data_404(
    empty_org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.get(ANALYTICS_BASE, headers=empty_org_admin_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYTICS_NOT_FOUND"


def test_filter_analytics_empty_message_200(
    empty_org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.post(
        f"{ANALYTICS_BASE}/filter",
        json={"filters": {"date_range": "2020-01-01 to 2030-12-31"}},
        headers=empty_org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total_sessions"] == 0
    assert "No analytics data" in body["message"]


def test_filter_analytics_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.post(
        f"{ANALYTICS_BASE}/filter",
        json=VALID_FILTERS,
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["filters"]["date_range"] == VALID_FILTERS["filters"]["date_range"]
    assert body["insights"]


def test_filter_invalid_parameters_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.post(
        f"{ANALYTICS_BASE}/filter",
        json={"filters": {"date_range": "invalid-range"}},
        headers=org_admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_export_analytics_csv_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.post(
        f"{ANALYTICS_BASE}/export",
        json={**VALID_FILTERS, "format": "csv"},
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Analytics insights exported successfully."
    assert body["format"] == "csv"
    assert body["content_base64"]
    assert body["filename"].endswith(".csv")


def test_export_analytics_pdf_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.post(
        f"{ANALYTICS_BASE}/export",
        json={**VALID_FILTERS, "format": "pdf"},
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "pdf"
    assert body["filename"].endswith(".pdf")


def test_analytics_forbidden_for_coach_403(
    coach_headers: dict[str, str],
    client: TestClient,
) -> None:
    response = client.get(ANALYTICS_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

def _expired_token(user_id) -> dict[str, str]:
    expired = jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {expired}"}


def test_analytics_missing_token_401(client: TestClient) -> None:
    response = client.get(ANALYTICS_BASE)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_analytics_expired_token_401(client: TestClient) -> None:
    response = client.get(ANALYTICS_BASE, headers=_expired_token(ORG_ADMIN_ID))
    assert response.status_code == 401


def test_analytics_insights_contain_trends(
    org_admin_headers: dict[str, str], client: TestClient
) -> None:
    response = client.get(ANALYTICS_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    insights = response.json()["insights"]
    assert isinstance(insights, list)
    assert len(insights) >= 1


def test_export_analytics_network_failure_502(
    org_admin_headers: dict[str, str], client: TestClient
) -> None:
    with patch(
        "app.services.org_analytics._build_csv_content",
        side_effect=RuntimeError("network error"),
    ):
        response = client.post(
            f"{ANALYTICS_BASE}/export",
            json={**VALID_FILTERS, "format": "csv"},
            headers=org_admin_headers,
        )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "EXPORT_FAILED"
