"""Stripe webhook processing with idempotent event handling."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stripe_webhook_event import StripeWebhookEvent
from app.models.subscription import StripeSubscription
from app.models.subscription_plan import SubscriptionPlan

logger = logging.getLogger(__name__)


async def is_webhook_event_processed(db: AsyncSession, stripe_event_id: str) -> bool:
    """Return True when the Stripe event ID was already processed."""
    result = await db.execute(
        select(StripeWebhookEvent.id).where(
            StripeWebhookEvent.stripe_event_id == stripe_event_id
        )
    )
    return result.scalar_one_or_none() is not None


async def mark_webhook_event_processed(
    db: AsyncSession,
    *,
    stripe_event_id: str,
    event_type: str,
) -> None:
    """Persist a processed Stripe event ID for idempotent webhook handling."""
    db.add(
        StripeWebhookEvent(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
        )
    )
    await db.commit()


async def sync_subscription_from_stripe(
    db: AsyncSession,
    *,
    stripe_subscription: dict,
) -> StripeSubscription | None:
    """Upsert local subscription state from a Stripe subscription payload."""
    stripe_subscription_id = stripe_subscription.get("id")
    if not stripe_subscription_id:
        return None

    result = await db.execute(
        select(StripeSubscription).where(
            StripeSubscription.stripe_subscription_id == stripe_subscription_id
        )
    )
    subscription = result.scalar_one_or_none()

    items = stripe_subscription.get("items", {}).get("data", [])
    stripe_price_id = items[0]["price"]["id"] if items else None
    status = stripe_subscription.get("status", "incomplete")
    customer_id = stripe_subscription.get("customer")
    metadata = stripe_subscription.get("metadata") or {}

    if subscription is None:
        plan_id_raw = metadata.get("plan_id")
        subscriber_email = metadata.get("subscriber_email")
        subscriber_user_id_raw = metadata.get("subscriber_user_id")
        if not plan_id_raw or not subscriber_email or not stripe_price_id or not customer_id:
            logger.warning(
                "Skipping unknown Stripe subscription %s — missing local metadata",
                stripe_subscription_id,
            )
            return None

        plan_result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == UUID(plan_id_raw))
        )
        plan = plan_result.scalar_one_or_none()
        if plan is None:
            logger.warning(
                "Stripe subscription %s references unknown plan %s",
                stripe_subscription_id,
                plan_id_raw,
            )
            return None

        subscription = StripeSubscription(
            plan_id=plan.id,
            subscriber_user_id=UUID(subscriber_user_id_raw) if subscriber_user_id_raw else None,
            subscriber_email=subscriber_email,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=str(customer_id),
            stripe_price_id=stripe_price_id,
            status=status,
        )
        db.add(subscription)
    else:
        subscription.status = status
        if stripe_price_id:
            subscription.stripe_price_id = stripe_price_id
            if subscription.pending_plan_id is not None and stripe_price_id:
                pending_plan = await db.execute(
                    select(SubscriptionPlan).where(
                        SubscriptionPlan.id == subscription.pending_plan_id
                    )
                )
                pending = pending_plan.scalar_one_or_none()
                if pending is not None and pending.stripe_price_id == stripe_price_id:
                    subscription.plan_id = pending.id
                    subscription.pending_plan_id = None

    await db.commit()
    await db.refresh(subscription)
    return subscription


async def sync_subscription_status_from_invoice(
    db: AsyncSession,
    *,
    invoice: dict,
) -> StripeSubscription | None:
    """Refresh local subscription status after a successful invoice payment."""
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return None

    result = await db.execute(
        select(StripeSubscription).where(
            StripeSubscription.stripe_subscription_id == str(subscription_id)
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        logger.info(
            "Invoice paid for unknown subscription %s — skipping local update",
            subscription_id,
        )
        return None

    subscription.status = "active"
    await db.commit()
    await db.refresh(subscription)
    logger.info("Marked subscription %s active after invoice.paid", subscription.id)
    return subscription
