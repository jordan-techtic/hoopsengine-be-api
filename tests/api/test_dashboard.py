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
    NEW_USER_EMAIL,
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


def _truncate_subscription_tables() -> None:
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE stripe_subscriptions_staging, "
                "subscription_plans_staging RESTART IDENTITY CASCADE"
            )
        )


def test_dashboard_loads_successfully_after_super_admin_login(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9600: Dashboard loads successfully after login."""
    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert isinstance(body["total_organizations"], int)


def test_get_dashboard_returns_200_with_analytics_data(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9600: Return 200 status with analytics data."""
    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    for key in _metric_keys():
        assert key in body
        assert isinstance(body[key], int)
        assert body[key] >= 0


def test_all_key_metrics_are_displayed_accurately(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9600: All key metrics are displayed accurately against seeded users/org."""
    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_organizations"] >= 1
    assert body["total_coaches"] == 2
    assert body["total_players"] == 1
    assert body["total_sessions"] >= 0
    assert body["active_subscriptions"] >= 0
    assert body["revenue_overview"] >= 0


def test_view_total_organizations_and_total_coaches(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9600 / FE: View Total Organizations and Total Coaches."""
    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert "total_organizations" in body
    assert "total_coaches" in body
    assert body["total_organizations"] >= 1
    assert body["total_coaches"] == 2


def test_super_admin_navigation_slots_are_client_side(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9600: Super Admin can navigate to core modules from the dashboard (FE-owned links)."""
    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["description"] is None
    assert body["link"] is None
    assert body["error"] is None


def test_get_dashboard_returns_200_when_no_session_or_subscription_data(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """Empty sessions/subscriptions are a successful empty state (HTTP 200)."""
    _truncate_subscription_tables()
    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_sessions"] >= 0
    assert body["active_subscriptions"] == 0
    assert body["revenue_overview"] == 0
    assert body["error"] is None


def test_get_dashboard_no_subscription_data_does_not_return_404(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """JAW-9600: Return 404 if no data is available — empty aggregates are 200, not 404."""
    _truncate_subscription_tables()
    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code != 404
    assert response.status_code == 200
    assert "total_organizations" in response.json()


def test_get_dashboard_unknown_subpath_returns_404(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """A missing dashboard sub-resource returns 404 with the standard error envelope."""
    response = client.get(f"{DASHBOARD_BASE}/does-not-exist", headers=admin_headers)
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert "error" in body
    assert body["error"]["code"]
    assert body["error"]["message"]


def test_get_dashboard_ignores_unknown_query_params(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """Unknown query strings do not fail GET dashboard."""
    response = client.get(
        f"{DASHBOARD_BASE}?search=&page=1&bogus=café",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert "total_organizations" in response.json()


def test_get_dashboard_post_method_not_allowed(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """POST is not a supported verb on the analytics endpoint."""
    response = client.post(DASHBOARD_BASE, headers=admin_headers, json={})
    assert response.status_code == 405
    body = response.json()
    assert body["success"] is False
    assert "error" in body


def test_get_dashboard_unauthorized_401_without_token(client: TestClient) -> None:
    """Missing Authorization header is rejected with 401."""
    response = client.get(DASHBOARD_BASE)
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}
    assert body["error"]["message"]


def test_get_dashboard_malformed_token_401(
    client: TestClient, seeded_users: dict
) -> None:
    """A non-JWT bearer token is rejected with 401."""
    response = client.get(
        DASHBOARD_BASE, headers=auth_headers("not-a-valid-jwt")
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


def test_get_dashboard_wrong_auth_scheme_401(
    client: TestClient, seeded_users: dict
) -> None:
    """Non-Bearer Authorization schemes are rejected."""
    response = client.get(
        DASHBOARD_BASE,
        headers={"Authorization": f"Token {seeded_users['admin']['token']}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] in {"MISSING_TOKEN", "INVALID_TOKEN"}


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


def test_new_user_not_in_database_cannot_call_dashboard(
    client: TestClient, new_user_payload: dict[str, str]
) -> None:
    """The registration-only new user has no JWT and is not in the database."""
    assert new_user_payload["email"] == NEW_USER_EMAIL
    response = client.get(DASHBOARD_BASE)
    assert response.status_code == 401


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
    """Live monthly+yearly subscriptions increment active_subscriptions and revenue_overview."""
    _truncate_subscription_tables()

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


def test_get_dashboard_past_due_counts_unpaid_does_not(
    client: TestClient, admin_headers: dict[str, str], seeded_users: dict
) -> None:
    """past_due is a live status; unpaid is not counted as an active subscription."""
    _truncate_subscription_tables()
    plan_id = uuid4()
    plan = SubscriptionPlan(
        id=plan_id,
        role=SubscriptionPlanRole.COACH.value,
        name="Coach Past Due",
        billing_frequency=BillingFrequency.MONTHLY.value,
        currency="USD",
        price_amount_cents=1900,
        stripe_product_id="prod_dash_pastdue",
        stripe_price_id="price_dash_pastdue",
        teams_limit_type=LimitType.UNLIMITED.value,
        players_limit_type=LimitType.UNLIMITED.value,
        historical_records_duration=HistoricalRecordsDuration.UNLIMITED.value,
        is_active=True,
        include_offline_sync=False,
        features=[],
    )
    past_due = StripeSubscription(
        plan_id=plan_id,
        subscriber_email="past-due@test.com",
        stripe_subscription_id="sub_dash_past_due",
        stripe_customer_id="cus_dash_pd",
        stripe_price_id="price_dash_pastdue",
        status=SubscriptionStatus.PAST_DUE.value,
    )
    unpaid = StripeSubscription(
        plan_id=plan_id,
        subscriber_email="unpaid@test.com",
        stripe_subscription_id="sub_dash_unpaid",
        stripe_customer_id="cus_dash_unpaid",
        stripe_price_id="price_dash_pastdue",
        status=SubscriptionStatus.UNPAID.value,
    )
    with Session(sync_engine) as session:
        session.add_all([plan, past_due, unpaid])
        session.commit()

    response = client.get(DASHBOARD_BASE, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["active_subscriptions"] == 1
    assert body["revenue_overview"] == 19
