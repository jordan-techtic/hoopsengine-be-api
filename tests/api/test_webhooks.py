"""Integration tests for Stripe webhook handling (HE-482)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import SubscriptionStatus
from app.models.stripe_webhook_event import StripeWebhookEvent
from app.models.subscription import StripeSubscription
from tests.api.test_dashboard import (
    _persist_plans_then_subscriptions,
    _truncate_subscription_tables,
)
from tests.api.test_subscription_management import (
    _coach_basic_plan,
    _coach_subscription,
)
from tests.conftest import WEBHOOKS_BASE, sync_engine


@pytest.fixture(autouse=True)
def _clean_subscription_tables() -> None:
    _truncate_subscription_tables()
    with Session(sync_engine) as session:
        session.query(StripeWebhookEvent).delete()
        session.commit()


def _subscription_updated_event(*, subscription_id: str, status: str = "active") -> dict:
    return {
        "id": f"evt_{uuid4().hex[:8]}",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": subscription_id,
                "customer": "cus_coach_current",
                "status": status,
                "metadata": {},
                "items": {"data": [{"price": {"id": "price_sub_basic"}}]},
            }
        },
    }


def test_stripe_webhook_rejects_missing_signature(client: TestClient) -> None:
    response = client.post(f"{WEBHOOKS_BASE}/stripe", content=b"{}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_STRIPE_SIGNATURE"


@patch("app.services.stripe_client.construct_webhook_event")
def test_stripe_webhook_rejects_invalid_signature(
    mock_construct: pytest.Mock,
    client: TestClient,
) -> None:
    mock_construct.side_effect = ValueError("invalid signature")
    response = client.post(
        f"{WEBHOOKS_BASE}/stripe",
        content=b"{}",
        headers={"stripe-signature": "bad"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_STRIPE_SIGNATURE"


@patch("app.services.stripe_client.construct_webhook_event")
def test_stripe_webhook_updates_subscription(
    mock_construct: pytest.Mock,
    client: TestClient,
) -> None:
    basic = _coach_basic_plan()
    subscription = _coach_subscription(plan_id=basic.id)
    stripe_subscription_id = subscription.stripe_subscription_id
    subscription_id = subscription.id
    _persist_plans_then_subscriptions([basic], [subscription])

    event = _subscription_updated_event(
        subscription_id=stripe_subscription_id,
        status="past_due",
    )
    mock_construct.return_value = event

    response = client.post(
        f"{WEBHOOKS_BASE}/stripe",
        content=b"{}",
        headers={"stripe-signature": "sig_test"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    with Session(sync_engine) as session:
        updated = session.get(StripeSubscription, subscription_id)
        assert updated is not None
        assert updated.status == "past_due"
        processed = (
            session.query(StripeWebhookEvent)
            .filter(StripeWebhookEvent.stripe_event_id == event["id"])
            .one_or_none()
        )
        assert processed is not None


@patch("app.services.stripe_client.construct_webhook_event")
def test_stripe_webhook_is_idempotent(
    mock_construct: pytest.Mock,
    client: TestClient,
) -> None:
    basic = _coach_basic_plan()
    subscription = _coach_subscription(plan_id=basic.id)
    stripe_subscription_id = subscription.stripe_subscription_id
    event_id = f"evt_{uuid4().hex[:8]}"
    _persist_plans_then_subscriptions([basic], [subscription])

    event = _subscription_updated_event(
        subscription_id=stripe_subscription_id,
        status="active",
    )
    event["id"] = event_id
    mock_construct.return_value = event

    first = client.post(
        f"{WEBHOOKS_BASE}/stripe",
        content=b"{}",
        headers={"stripe-signature": "sig_test"},
    )
    second = client.post(
        f"{WEBHOOKS_BASE}/stripe",
        content=b"{}",
        headers={"stripe-signature": "sig_test"},
    )
    assert first.status_code == 200
    assert second.status_code == 200

    with Session(sync_engine) as session:
        count = (
            session.query(StripeWebhookEvent)
            .filter(StripeWebhookEvent.stripe_event_id == event["id"])
            .count()
        )
        assert count == 1


@patch("app.services.stripe_client.construct_webhook_event")
def test_stripe_webhook_invoice_paid_marks_subscription_active(
    mock_construct: pytest.Mock,
    client: TestClient,
) -> None:
    basic = _coach_basic_plan()
    subscription = _coach_subscription(plan_id=basic.id)
    subscription.status = SubscriptionStatus.PAST_DUE.value
    stripe_subscription_id = subscription.stripe_subscription_id
    subscription_id = subscription.id
    _persist_plans_then_subscriptions([basic], [subscription])

    event = {
        "id": f"evt_{uuid4().hex[:8]}",
        "type": "invoice.paid",
        "data": {
            "object": {
                "subscription": stripe_subscription_id,
            }
        },
    }
    mock_construct.return_value = event

    response = client.post(
        f"{WEBHOOKS_BASE}/stripe",
        content=b"{}",
        headers={"stripe-signature": "sig_test"},
    )
    assert response.status_code == 200

    with Session(sync_engine) as session:
        updated = session.get(StripeSubscription, subscription_id)
        assert updated is not None
        assert updated.status == SubscriptionStatus.ACTIVE.value
