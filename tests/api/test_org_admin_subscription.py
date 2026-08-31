"""Integration tests for organization admin subscription management API (HE-408)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import (
    BillingFrequency,
    HistoricalRecordsDuration,
    LimitType,
    SubscriptionPlanRole,
    SubscriptionStatus,
    UserRole,
)
from app.models.subscription import StripeSubscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from tests.api.test_dashboard import _persist_plans_then_subscriptions, _truncate_subscription_tables
from tests.api.test_subscription_management import PRO_FEATURES
from tests.conftest import (
    ORG_ADMIN_SUBSCRIPTION_BASE,
    REGULAR_USER_ID,
    SEEDED_ORG_ID,
    auth_headers,
    create_access_token,
    sync_engine,
)

ORG_ADMIN_ID = UUID("00000000-0000-4000-8000-000000000091")


@pytest.fixture(autouse=True)
def _clean_subscription_tables() -> None:
    _truncate_subscription_tables()


@pytest.fixture
def org_admin_headers(seeded_users: dict) -> dict[str, str]:
    """Bearer token for an org_admin user linked to the seeded organization."""
    with Session(sync_engine) as session:
        if session.get(User, ORG_ADMIN_ID) is None:
            session.add(
                User(
                    id=ORG_ADMIN_ID,
                    email="orgadmin.subscription@test.com",
                    username="orgadminsub",
                    encrypted_password=hash_password("OrgAdmin123!"),
                    role=UserRole.ORG_ADMIN.value,
                    first_name="Jane",
                    last_name="Doe",
                    is_super_admin=False,
                    is_active=True,
                    org_id=SEEDED_ORG_ID,
                    email_confirmed_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
    return auth_headers(create_access_token(ORG_ADMIN_ID))


@pytest.fixture
def coach_headers(seeded_users: dict) -> dict[str, str]:
    return auth_headers(create_access_token(REGULAR_USER_ID))


def _org_basic_plan(plan_id: UUID | None = None) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=plan_id or uuid4(),
        role=SubscriptionPlanRole.ORG_ADMIN.value,
        name="Basic Plan",
        billing_frequency=BillingFrequency.MONTHLY.value,
        currency="USD",
        price_amount_cents=9900,
        stripe_product_id="prod_org_basic",
        stripe_price_id="price_org_basic",
        teams_limit_type=LimitType.LIMITED.value,
        teams_count=3,
        players_limit_type=LimitType.LIMITED.value,
        players_count=50,
        historical_records_duration=HistoricalRecordsDuration.SIX_MONTHS.value,
        is_active=True,
        include_offline_sync=False,
        features=["Basic Organization Features"],
    )


def _org_pro_plan(plan_id: UUID | None = None) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=plan_id or uuid4(),
        role=SubscriptionPlanRole.ORG_ADMIN.value,
        name="Pro Plan",
        billing_frequency=BillingFrequency.MONTHLY.value,
        currency="USD",
        price_amount_cents=19900,
        stripe_product_id="prod_org_pro",
        stripe_price_id="price_org_pro",
        teams_limit_type=LimitType.LIMITED.value,
        teams_count=5,
        players_limit_type=LimitType.UNLIMITED.value,
        historical_records_duration=HistoricalRecordsDuration.UNLIMITED.value,
        is_active=True,
        include_offline_sync=True,
        features=PRO_FEATURES,
    )


def _org_admin_subscription(*, plan_id: UUID) -> StripeSubscription:
    return StripeSubscription(
        id=uuid4(),
        plan_id=plan_id,
        subscriber_user_id=ORG_ADMIN_ID,
        subscriber_email="orgadmin.subscription@test.com",
        stripe_subscription_id="sub_org_admin_current",
        stripe_customer_id="cus_org_admin_current",
        stripe_price_id="price_org_basic",
        status=SubscriptionStatus.ACTIVE.value,
    )


def test_get_org_subscription_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    basic = _org_basic_plan()
    subscription = _org_admin_subscription(plan_id=basic.id)
    _persist_plans_then_subscriptions([basic], [subscription])

    response = client.get(ORG_ADMIN_SUBSCRIPTION_BASE, headers=org_admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["subscription_plan"] == "Basic Plan"
    assert body["name"] == "Basic Plan"
    assert body["billing_cycle"] == "monthly"
    assert body["features_included"] == ["Basic Organization Features"]
    assert body["full_name"] == "Jane Doe"
    assert body["renewal_date"]
    assert body["notification"]
    assert body["title"] == "Subscription Management"


def test_upgrade_org_subscription_200(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    basic = _org_basic_plan()
    pro = _org_pro_plan()
    pro_id = pro.id
    subscription = _org_admin_subscription(plan_id=basic.id)
    _persist_plans_then_subscriptions([basic, pro], [subscription])

    response = client.post(
        f"{ORG_ADMIN_SUBSCRIPTION_BASE}/upgrade",
        headers=org_admin_headers,
        json={"full_name": "Pro Plan"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["subscription_plan"] == "Pro Plan"
    assert body["features_included"] == PRO_FEATURES
    assert body["message"] == "Subscription upgraded successfully"
    assert body["notification"] == "Subscription upgraded successfully"


def test_upgrade_org_subscription_400_invalid_plan(
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    basic = _org_basic_plan()
    subscription = _org_admin_subscription(plan_id=basic.id)
    _persist_plans_then_subscriptions([basic], [subscription])

    response = client.post(
        f"{ORG_ADMIN_SUBSCRIPTION_BASE}/upgrade",
        headers=org_admin_headers,
        json={"plan_id": "00000000-0000-4000-8000-000000000099"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


@patch(
    "app.services.subscription_management.stripe_client.get_subscription_current_period_end",
    return_value=int((datetime.now(timezone.utc) + timedelta(days=3)).timestamp()),
)
def test_upgrade_org_subscription_renewal_warning(
    _mock_period_end: pytest.Mock,
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    basic = _org_basic_plan()
    pro = _org_pro_plan()
    subscription = _org_admin_subscription(plan_id=basic.id)
    _persist_plans_then_subscriptions([basic, pro], [subscription])

    response = client.post(
        f"{ORG_ADMIN_SUBSCRIPTION_BASE}/upgrade",
        headers=org_admin_headers,
        json={"full_name": "Pro Plan"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["warning"]
    assert "5 days" in body["warning"]
    assert body["notification"] == "Subscription upgraded successfully"


def test_org_subscription_forbidden_coach_403(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(ORG_ADMIN_SUBSCRIPTION_BASE, headers=coach_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@patch("app.services.subscription_management.stripe_client.stripe_configured", return_value=False)
def test_upgrade_org_subscription_503_stripe_not_configured(
    _mock_stripe_configured: pytest.Mock,
    client: TestClient,
    org_admin_headers: dict[str, str],
) -> None:
    basic = _org_basic_plan()
    pro = _org_pro_plan()
    subscription = _org_admin_subscription(plan_id=basic.id)
    _persist_plans_then_subscriptions([basic, pro], [subscription])

    response = client.post(
        f"{ORG_ADMIN_SUBSCRIPTION_BASE}/upgrade",
        headers=org_admin_headers,
        json={"full_name": "Pro Plan"},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "STRIPE_NOT_CONFIGURED"
