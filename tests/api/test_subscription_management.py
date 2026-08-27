"""Integration tests for coach subscription management API."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import (
    BillingFrequency,
    HistoricalRecordsDuration,
    LimitType,
    SubscriptionPlanRole,
    SubscriptionStatus,
)
from app.models.subscription import StripeSubscription
from app.models.subscription_plan import SubscriptionPlan
from tests.api.test_dashboard import _persist_plans_then_subscriptions, _truncate_subscription_tables
from tests.conftest import REGULAR_EMAIL, REGULAR_USER_ID, SUBSCRIPTION_BASE, sync_engine

PRO_FEATURES = [
    "Unlimited Drill Library Access",
    "Team Management (up to 5 teams)",
    "Advanced Performance Analytics",
    "Priority Coach Support",
]


@pytest.fixture(autouse=True)
def _clean_subscription_tables() -> None:
    _truncate_subscription_tables()


def _coach_basic_plan(plan_id: UUID | None = None) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=plan_id or uuid4(),
        role=SubscriptionPlanRole.COACH.value,
        name="Basic Plan",
        billing_frequency=BillingFrequency.MONTHLY.value,
        currency="USD",
        price_amount_cents=1900,
        stripe_product_id="prod_sub_basic",
        stripe_price_id="price_sub_basic",
        teams_limit_type=LimitType.LIMITED.value,
        teams_count=1,
        players_limit_type=LimitType.LIMITED.value,
        players_count=15,
        historical_records_duration=HistoricalRecordsDuration.THREE_MONTHS.value,
        is_active=True,
        include_offline_sync=False,
        features=["Basic Drill Library Access"],
    )


def _coach_pro_plan(plan_id: UUID | None = None) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=plan_id or uuid4(),
        role=SubscriptionPlanRole.COACH.value,
        name="Pro Plan",
        billing_frequency=BillingFrequency.MONTHLY.value,
        currency="USD",
        price_amount_cents=4900,
        stripe_product_id="prod_sub_pro",
        stripe_price_id="price_sub_pro",
        teams_limit_type=LimitType.LIMITED.value,
        teams_count=5,
        players_limit_type=LimitType.UNLIMITED.value,
        historical_records_duration=HistoricalRecordsDuration.UNLIMITED.value,
        is_active=True,
        include_offline_sync=True,
        features=PRO_FEATURES,
    )


def _coach_subscription(*, plan_id: UUID) -> StripeSubscription:
    return StripeSubscription(
        id=uuid4(),
        plan_id=plan_id,
        subscriber_user_id=REGULAR_USER_ID,
        subscriber_email=REGULAR_EMAIL,
        stripe_subscription_id="sub_coach_current",
        stripe_customer_id="cus_coach_current",
        stripe_price_id="price_sub_basic",
        status=SubscriptionStatus.ACTIVE.value,
    )


def test_get_subscription_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    basic = _coach_basic_plan()
    subscription = _coach_subscription(plan_id=basic.id)
    _persist_plans_then_subscriptions([basic], [subscription])

    response = client.get(SUBSCRIPTION_BASE, headers=coach_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["title"] == "Subscription"
    assert body["current_plan"] == "Basic Plan"
    assert body["name"] == "Basic Plan"
    assert body["full_name"] == "Regular Coach"
    assert body["features"] == ["Basic Drill Library Access"]
    assert body["expiry_date"]
    assert body["status"] == "active"


def test_get_subscription_404(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.get(SUBSCRIPTION_BASE, headers=coach_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SUBSCRIPTION_NOT_FOUND"


def test_upgrade_subscription_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    basic = _coach_basic_plan()
    pro = _coach_pro_plan()
    basic_id = basic.id
    pro_id = pro.id
    subscription = _coach_subscription(plan_id=basic_id)
    subscription_id = subscription.id
    _persist_plans_then_subscriptions([basic, pro], [subscription])

    response = client.post(
        f"{SUBSCRIPTION_BASE}/upgrade",
        headers=coach_headers,
        json={"plan_id": str(pro_id), "full_name": "Jane Doe"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["current_plan"] == "Pro Plan"
    assert body["features"] == PRO_FEATURES
    assert body["message"] == "Subscription upgraded successfully"

    with Session(sync_engine) as session:
        updated = session.get(StripeSubscription, subscription_id)
        assert updated is not None
        assert updated.plan_id == pro_id
        assert updated.stripe_price_id == "price_sub_pro"


def test_upgrade_subscription_400_invalid_plan(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    basic = _coach_basic_plan()
    subscription = _coach_subscription(plan_id=basic.id)
    _persist_plans_then_subscriptions([basic], [subscription])

    response = client.post(
        f"{SUBSCRIPTION_BASE}/upgrade",
        headers=coach_headers,
        json={"plan_id": "00000000-0000-4000-8000-000000000099"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_upgrade_subscription_400_same_plan(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    basic = _coach_basic_plan()
    basic_id = basic.id
    subscription = _coach_subscription(plan_id=basic_id)
    _persist_plans_then_subscriptions([basic], [subscription])

    response = client.post(
        f"{SUBSCRIPTION_BASE}/upgrade",
        headers=coach_headers,
        json={"plan_id": str(basic_id)},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_cancel_subscription_200(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    pro = _coach_pro_plan()
    pro_id = pro.id
    subscription = _coach_subscription(plan_id=pro_id)
    subscription_id = subscription.id
    subscription.stripe_price_id = "price_sub_pro"
    _persist_plans_then_subscriptions([pro], [subscription])

    response = client.post(
        f"{SUBSCRIPTION_BASE}/cancel",
        headers=coach_headers,
        json={"full_name": "Jane Doe"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "canceled"
    assert body["message"] == "Subscription canceled successfully"

    with Session(sync_engine) as session:
        updated = session.get(StripeSubscription, subscription_id)
        assert updated is not None
        assert updated.status == SubscriptionStatus.CANCELED.value


def test_cancel_subscription_404(
    client: TestClient,
    coach_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{SUBSCRIPTION_BASE}/cancel",
        headers=coach_headers,
        json={},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SUBSCRIPTION_NOT_FOUND"


def test_subscription_endpoints_403_without_auth(client: TestClient) -> None:
    response = client.get(SUBSCRIPTION_BASE)
    assert response.status_code == 403
