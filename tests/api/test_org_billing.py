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
    TEST_VALID_PASSWORD,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000056")
ORG_ADMIN_PASSWORD = TEST_VALID_PASSWORD

VALID_PAYMENT_METHOD = {
    "stripe_payment_method_id": "pm_test_4242",
}

MOCK_PAYMENT_METHOD = {
    "id": "pm_test_4242",
    "brand": "visa",
    "last4": "4242",
    "exp_month": 12,
    "exp_year": 2028,
}

MOCK_INVOICES = [
    {
        "id": "in_test_paid",
        "amount_due": 9900,
        "amount_paid": 9900,
        "currency": "USD",
        "status": "paid",
        "created": int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp()),
    },
    {
        "id": "in_test_pending",
        "amount_due": 9900,
        "amount_paid": 0,
        "currency": "USD",
        "status": "open",
        "created": int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp()),
    },
]


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
                encrypted_password=hash_password(ORG_ADMIN_PASSWORD),
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
                    description="stripe_invoice:in_test_paid",
                ),
                OrgBillingHistory(
                    org_id=SEEDED_ORG_ID,
                    billing_date=date(2026, 9, 1),
                    amount_cents=9900,
                    status="pending",
                    description="stripe_invoice:in_test_pending",
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
            "app.services.org_billing.stripe_client.retrieve_payment_method_metadata",
            return_value=MOCK_PAYMENT_METHOD,
        ),
        patch(
            "app.services.org_billing.stripe_client.attach_payment_method_to_customer",
            return_value=None,
        ),
        patch(
            "app.services.org_billing.stripe_client.list_customer_invoices",
            return_value=MOCK_INVOICES,
        ),
    ):
        yield


def test_get_billing_history_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
    seeded_billing_history: None,
    mock_stripe_billing: None,
) -> None:
    response = client.get(BILLING_HISTORY_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Billing history loaded successfully."
    assert len(body["data"]["billing_history"]) >= 1
    assert len(body["data"]["upcoming_payments"]) >= 1


def test_get_billing_history_404(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    with Session(sync_engine) as session:
        session.query(OrgBillingHistory).filter(
            OrgBillingHistory.org_id == SEEDED_ORG_ID
        ).delete()
        session.commit()
    with patch("app.services.org_billing.stripe_client.stripe_configured", return_value=False):
        response = client.get(BILLING_HISTORY_BASE, headers=org_admin_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BILLING_HISTORY_NOT_FOUND"


def test_get_billing_history_alias_200(
    org_admin_headers: dict[str, str],
    client: TestClient,
    seeded_billing_history: None,
    mock_stripe_billing: None,
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


def test_update_payment_method_missing_token_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
    mock_stripe_billing: None,
) -> None:
    response = client.post(
        BILLING_PAYMENT_METHOD_BASE,
        json={"stripe_payment_method_id": ""},
        headers=org_admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"][0]["field"] == "stripe_payment_method_id"


def test_update_payment_method_invalid_token_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
    mock_stripe_billing: None,
) -> None:
    response = client.post(
        BILLING_PAYMENT_METHOD_BASE,
        json={"stripe_payment_method_id": "not-a-pm-token"},
        headers=org_admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_billing_forbidden_coach_403(
    coach_headers: dict[str, str],
    client: TestClient,
    seeded_billing_history: None,
) -> None:
    response = client.get(BILLING_HISTORY_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"

def test_get_billing_history_includes_notifications(
    org_admin_headers: dict[str, str],
    client: TestClient,
    seeded_billing_history: None,
    mock_stripe_billing: None,
) -> None:
    response = client.get(BILLING_HISTORY_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    notifications = response.json()["data"]["notifications"]
    assert len(notifications) >= 1
    assert notifications[0]["type"] == "upcoming_payment"


def test_billing_missing_token_401(client: TestClient) -> None:
    response = client.get(BILLING_HISTORY_BASE)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "MISSING_TOKEN"


def test_update_payment_method_stripe_failure_400(
    org_admin_headers: dict[str, str],
    client: TestClient,
) -> None:
    with (
        patch("app.services.org_billing.stripe_client.stripe_configured", return_value=True),
        patch(
            "app.services.org_billing.stripe_client.retrieve_payment_method_metadata",
            side_effect=RuntimeError("stripe unavailable"),
        ),
    ):
        response = client.post(
            BILLING_PAYMENT_METHOD_BASE,
            json=VALID_PAYMENT_METHOD,
            headers=org_admin_headers,
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PAYMENT_METHOD_INVALID"
