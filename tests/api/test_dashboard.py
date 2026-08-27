"""Integration tests for Super Admin Dashboard analytics API (JAW-9600)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
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
from app.models.user import User
from tests.conftest import (
    ADMIN_ID,
    REGULAR_USER_ID,
    auth_headers,
    make_expired_token,
    sync_engine,
)

DASHBOARD_BASE = "/api/v1/super-admin/dashboard"


def _metric_keys() -> tuple[str, ...]:
    return (
        "total_organizations",
        "total_coaches",
        "total_players",
        "total_sessions",
        "active_subscriptions",
        "revenue_overview",
    )


def test_get_dashboard_returns_200_with_analytics_data(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9600: Return 200 status with analytics data after super-admin login."""
    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    for key in _metric_keys():
        assert key in body
        assert isinstance(body[key], int)
        assert body[key] >= 0
    assert body["total_organizations"] >= 1
    assert body["total_coaches"] == 2
    assert body["total_players"] == 1
    assert body["total_sessions"] == 0
    assert body["active_subscriptions"] == 0
    assert body["revenue_overview"] == 0
    assert body["description"] is None
    assert body["link"] is None
    assert body["error"] is None


def test_get_dashboard_returns_200_when_session_and_subscription_counts_are_zero(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9600: Empty sessions/subscriptions are a 200 empty state, not 404."""
    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_sessions"] == 0
    assert body["active_subscriptions"] == 0
    assert body["revenue_overview"] == 0
    assert body["error"] is None


def test_get_dashboard_unauthorized_401_without_token(client: TestClient) -> None:
    """Missing Authorization header is rejected with 401."""
    response = client.get(DASHBOARD_BASE)
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}
    assert body["error"]["message"]


def test_get_dashboard_forbidden_403_for_coach(
    client: TestClient, user_headers: dict[str, str]
) -> None:
    """A coach cannot read Super Admin dashboard analytics."""
    response = client.get(DASHBOARD_BASE, headers=user_headers)
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"
    assert body["error"]["message"]


def test_get_dashboard_forbidden_403_for_player(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    """A player cannot read Super Admin dashboard analytics."""
    response = client.get(DASHBOARD_BASE, headers=viewer_headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_get_dashboard_unauthorized_401_expired_token(
    client: TestClient, seeded_users: dict
) -> None:
    """An expired access token is rejected with 401."""
    token = make_expired_token(seeded_users["admin"]["id"])
    response = client.get(DASHBOARD_BASE, headers=auth_headers(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_get_dashboard_inactive_user_401(
    client: TestClient, inactive_headers: dict[str, str]
) -> None:
    """A deactivated account cannot call the dashboard."""
    response = client.get(DASHBOARD_BASE, headers=inactive_headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_get_dashboard_excludes_soft_deleted_coaches(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """Soft-deleted coach accounts are omitted from total_coaches."""
    with Session(sync_engine) as session:
        coach = session.get(User, REGULAR_USER_ID)
        assert coach is not None
        coach.deleted_at = datetime.now(timezone.utc)
        session.commit()

    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total_coaches"] == 1


def test_get_dashboard_active_subscription_and_revenue(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """Live monthly subscriptions increment active_subscriptions and revenue_overview."""
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE stripe_subscriptions_staging, "
                "subscription_plans_staging RESTART IDENTITY CASCADE"
            )
        )

    monthly_plan_id = uuid4()
    yearly_plan_id = uuid4()
    monthly_plan = SubscriptionPlan(
        id=monthly_plan_id,
        role=SubscriptionPlanRole.COACH.value,
        name="Coach Monthly",
        billing_frequency=BillingFrequency.MONTHLY.value,
        currency="USD",
        price_amount_cents=4900,
        stripe_product_id="prod_dash_monthly",
        stripe_price_id="price_dash_monthly",
        teams_limit_type=LimitType.UNLIMITED.value,
        players_limit_type=LimitType.UNLIMITED.value,
        historical_records_duration=HistoricalRecordsDuration.UNLIMITED.value,
        is_active=True,
        include_offline_sync=False,
        features=[],
    )
    yearly_plan = SubscriptionPlan(
        id=yearly_plan_id,
        role=SubscriptionPlanRole.ORG_ADMIN.value,
        name="Org Yearly",
        billing_frequency=BillingFrequency.YEARLY.value,
        currency="USD",
        price_amount_cents=120000,
        stripe_product_id="prod_dash_yearly",
        stripe_price_id="price_dash_yearly",
        teams_limit_type=LimitType.UNLIMITED.value,
        coaches_limit_type=LimitType.UNLIMITED.value,
        players_limit_type=LimitType.UNLIMITED.value,
        historical_records_duration=HistoricalRecordsDuration.UNLIMITED.value,
        is_active=True,
        include_offline_sync=False,
        features=[],
    )
    active_monthly = StripeSubscription(
        plan_id=monthly_plan_id,
        subscriber_user_id=ADMIN_ID,
        subscriber_email="active-monthly@test.com",
        stripe_subscription_id="sub_dash_active_monthly",
        stripe_customer_id="cus_dash_1",
        stripe_price_id="price_dash_monthly",
        status=SubscriptionStatus.ACTIVE.value,
    )
    active_yearly = StripeSubscription(
        plan_id=yearly_plan_id,
        subscriber_email="active-yearly@test.com",
        stripe_subscription_id="sub_dash_active_yearly",
        stripe_customer_id="cus_dash_2",
        stripe_price_id="price_dash_yearly",
        status=SubscriptionStatus.TRIALING.value,
    )
    canceled = StripeSubscription(
        plan_id=monthly_plan_id,
        subscriber_email="canceled@test.com",
        stripe_subscription_id="sub_dash_canceled",
        stripe_customer_id="cus_dash_3",
        stripe_price_id="price_dash_monthly",
        status=SubscriptionStatus.CANCELED.value,
    )

    with Session(sync_engine) as session:
        session.add_all(
            [monthly_plan, yearly_plan, active_monthly, active_yearly, canceled]
        )
        session.commit()

    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["active_subscriptions"] == 2
    assert body["revenue_overview"] == 149
