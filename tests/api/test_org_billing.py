"""Integration tests for organization admin billing API (HE-448)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.org_billing import OrgBillingHistory
from app.models.user import User
from tests.conftest import (
    BILLING_HISTORY_ALIAS_BASE,
    BILLING_HISTORY_BASE,
    BILLING_PAYMENT_METHOD_ALIAS_BASE,
    BILLING_PAYMENT_METHOD_BASE,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000055")

VALID_PAYMENT_METHOD = {
    "card_number": "4242424242424242",
    "expiry_date": "12/28",
    "cvv": "123",
}

MOCK_PAYMENT_METHOD = {
    "id": "pm_test_4242",
    "brand": "visa",
    "last4": "4242",
    "exp_month": 12,
    "exp_year": 2028,
}


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        existing = session.get(User, ORG_ADMIN_ID)
        if existing is None:
            org_admin = User(
                id=ORG_ADMIN_ID,
                email="orgadmin.billing@test.com",
                username="orgadminbilling",
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


@pytest.fixture
def seeded_billing_history(seeded_users: dict) -> None:
    """Seed billing history rows for the seeded organization."""
    with Session(sync_engine) as session:
        session.query(OrgBillingHistory).filter(
            OrgBillingHistory.org_id == SEEDED_ORG_ID
        ).delete()
        session.add_all(
            [
                OrgBillingHistory(
                    org_id=SEEDED_ORG_ID,
                    billing_date=date(2026, 7, 1),
                    amount_cents=9900,
                    status="paid",
                    description="Monthly subscription",
                ),
                OrgBillingHistory(
                    org_id=SEEDED_ORG_ID,
                    billing_date=date(2026, 9, 1),
                    amount_cents=9900,
                    status="pending",
                    description="Upcoming subscription charge",
                ),
            ]
        )
        session.commit()


@pytest.fixture
def mock_stripe_billing():
    """Mock Stripe payment method operations for billing tests."""
    with (
        patch("app.services.org_billing.stripe_client.stripe_configured", return_value=True),
        patch(
            "app.services.org_billing.stripe_client.create_stripe_customer",
            return_value="cus_test_billing",
        ),
        patch(
            "app.services.org_billing.stripe_client.create_card_payment_method",
            return_value=MOCK_PAYMENT_METHOD,
        ),
        patch(
            "app.services.org_billing.stripe_client.attach_payment_method_to_customer",
            return_value=None,
        ),
    ):
        yield


def test_get_billing_history_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
    seeded_billing_history: None,
) -> None:
    response = client.get(BILLING_HISTORY_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Billing history loaded successfully."
    assert len(body["data"]["billing_history"]) == 1
    assert body["data"]["billing_history"][0]["status"] == "paid"
    assert len(body["data"]["upcoming_payments"]) == 1
    assert body["data"]["upcoming_payments"][0]["status"] == "pending"
    assert len(body["data"]["notifications"]) == 1


def test_get_billing_history_404(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    with Session(sync_engine) as session:
        session.query(OrgBillingHistory).filter(
            OrgBillingHistory.org_id == SEEDED_ORG_ID
        ).delete()
        session.commit()
    response = client.get(BILLING_HISTORY_BASE, headers=org_admin_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BILLING_HISTORY_NOT_FOUND"


def test_get_billing_history_alias_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
    seeded_billing_history: None,
) -> None:
    response = client.get(BILLING_HISTORY_ALIAS_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_update_payment_method_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
    mock_stripe_billing: None,
) -> None:
    response = client.post(
        BILLING_PAYMENT_METHOD_BASE,
        json=VALID_PAYMENT_METHOD,
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Payment method updated successfully."
    assert body["data"]["card_last4"] == "4242"
    assert body["data"]["expiry_date"] == "12/28"


def test_update_payment_method_alias_put_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
    mock_stripe_billing: None,
) -> None:
    response = client.put(
        BILLING_PAYMENT_METHOD_ALIAS_BASE,
        json=VALID_PAYMENT_METHOD,
        headers=org_admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Payment method updated successfully."


def test_update_payment_method_missing_card_number_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
    mock_stripe_billing: None,
) -> None:
    payload = dict(VALID_PAYMENT_METHOD)
    payload["card_number"] = ""
    response = client.post(
        BILLING_PAYMENT_METHOD_BASE,
        json=payload,
        headers=org_admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"][0]["field"] == "card_number"


def test_update_payment_method_invalid_card_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
    mock_stripe_billing: None,
) -> None:
    payload = dict(VALID_PAYMENT_METHOD)
    payload["card_number"] = "4111111111111112"
    response = client.post(
        BILLING_PAYMENT_METHOD_BASE,
        json=payload,
        headers=org_admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_update_payment_method_missing_cvv_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
    mock_stripe_billing: None,
) -> None:
    payload = dict(VALID_PAYMENT_METHOD)
    payload["cvv"] = ""
    response = client.post(
        BILLING_PAYMENT_METHOD_BASE,
        json=payload,
        headers=org_admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "cvv"


def test_billing_forbidden_coach_403(
    coach_headers: dict[str, str],
    client: TestClient,
    seeded_billing_history: None,
) -> None:
    response = client.get(BILLING_HISTORY_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
