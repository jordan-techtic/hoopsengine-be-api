"""Business logic for coach subscription management."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.enums import SubscriptionPlanRole, SubscriptionStatus, UserRole
from app.models.subscription import StripeSubscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.schemas.subscription_management import (
    SubscriptionCancelRequest,
    SubscriptionUpgradeRequest,
)
from app.services import stripe_client
from app.services.subscription_plan import ACTIVE_SUBSCRIPTION_STATUSES

logger = logging.getLogger(__name__)

DEFAULT_FEATURES = [
    "Unlimited Drill Library Access",
    "Team Management (up to 5 teams)",
    "Advanced Performance Analytics",
    "Priority Coach Support",
]


def _user_full_name(user: User) -> str:
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(part.strip() for part in parts if part and part.strip()).strip()
    return name or (user.username or "Subscriber")


def _format_expiry_date(value: datetime) -> str:
    return value.strftime("%b %d, %Y")


def _plan_features(plan: SubscriptionPlan) -> list[str]:
    raw = plan.features or []
    if isinstance(raw, list) and raw:
        return [str(item) for item in raw]
    if plan.description:
        return [plan.description]
    return list(DEFAULT_FEATURES)


def _subscription_role_for_user(user: User) -> SubscriptionPlanRole:
    if user.role == UserRole.ORG_ADMIN.value:
        return SubscriptionPlanRole.ORG_ADMIN
    return SubscriptionPlanRole.COACH


async def _get_target_plan(
    db: AsyncSession,
    *,
    plan_id: UUID,
    role: SubscriptionPlanRole,
) -> SubscriptionPlan:
    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.role == role.value,
            SubscriptionPlan.deleted_at.is_(None),
            SubscriptionPlan.archived_at.is_(None),
            SubscriptionPlan.is_active.is_(True),
        )
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Invalid subscription plan selected",
            status_code=400,
            details=[{"field": "plan_id", "message": "Subscription plan is invalid or unavailable"}],
        )
    return plan


async def _get_owned_subscription(db: AsyncSession, user: User) -> StripeSubscription:
    result = await db.execute(
        select(StripeSubscription)
        .where(
            or_(
                StripeSubscription.subscriber_user_id == user.id,
                and_(
                    StripeSubscription.subscriber_user_id.is_(None),
                    StripeSubscription.subscriber_email == user.email,
                ),
            )
        )
        .order_by(StripeSubscription.created_at.desc())
        .limit(1)
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise AppException(
            code="SUBSCRIPTION_NOT_FOUND",
            message="No subscription found for this account",
            status_code=404,
        )

    if (
        subscription.subscriber_user_id is not None
        and subscription.subscriber_user_id != user.id
    ):
        raise AppException(
            code="FORBIDDEN",
            message="You do not have permission to manage this subscription",
            status_code=403,
        )

    return subscription


async def _load_plan(db: AsyncSession, plan_id: UUID) -> SubscriptionPlan:
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise AppException(
            code="SUBSCRIPTION_NOT_FOUND",
            message="Subscription plan details are unavailable",
            status_code=404,
        )
    return plan


async def _resolve_expiry_date(subscription: StripeSubscription) -> datetime:
    if stripe_client.stripe_configured():
        try:
            period_end = stripe_client.get_subscription_current_period_end(
                subscription.stripe_subscription_id
            )
            if period_end:
                return datetime.fromtimestamp(period_end, tz=timezone.utc)
        except Exception:
            logger.exception(
                "Failed to resolve Stripe period end for subscription %s",
                subscription.stripe_subscription_id,
            )

    return subscription.updated_at + timedelta(days=30)


def _subscription_to_response(
    *,
    subscription: StripeSubscription,
    plan: SubscriptionPlan,
    user: User,
    message: str,
    description: str,
    expiry_date: str,
) -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "status": subscription.status,
        "description": description,
        "link": None,
        "error": None,
        "id": subscription.id,
        "title": "Subscription",
        "name": plan.name,
        "current_plan": plan.name,
        "expiry_date": expiry_date,
        "features": _plan_features(plan),
        "full_name": _user_full_name(user),
    }


async def _build_subscription_response(
    db: AsyncSession,
    *,
    subscription: StripeSubscription,
    user: User,
    message: str,
    description: str,
) -> dict[str, Any]:
    plan = await _load_plan(db, subscription.plan_id)
    expiry_dt = await _resolve_expiry_date(subscription)
    return _subscription_to_response(
        subscription=subscription,
        plan=plan,
        user=user,
        message=message,
        description=description,
        expiry_date=_format_expiry_date(expiry_dt),
    )


async def get_current_subscription(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return the authenticated user's current subscription details."""
    subscription = await _get_owned_subscription(db, user)
    description = (
        "Your current subscription is active"
        if subscription.status in ACTIVE_SUBSCRIPTION_STATUSES
        else "Your subscription is no longer active"
    )
    return await _build_subscription_response(
        db,
        subscription=subscription,
        user=user,
        message="Subscription details loaded successfully",
        description=description,
    )


async def upgrade_subscription(
    db: AsyncSession,
    user: User,
    payload: SubscriptionUpgradeRequest,
) -> dict[str, Any]:
    """Upgrade the authenticated user's subscription to another active plan."""
    subscription = await _get_owned_subscription(db, user)
    role = _subscription_role_for_user(user)
    target_plan = await _get_target_plan(db, plan_id=payload.plan_id, role=role)

    if subscription.plan_id == target_plan.id:
        raise AppException(
            code="VALIDATION_ERROR",
            message="You are already subscribed to this plan",
            status_code=400,
            details=[{"field": "plan_id", "message": "Select a different plan to upgrade"}],
        )

    if subscription.status not in ACTIVE_SUBSCRIPTION_STATUSES:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Only active subscriptions can be upgraded",
            status_code=400,
            details=[{"field": "plan_id", "message": "Your subscription is not active"}],
        )

    if stripe_client.stripe_configured():
        try:
            stripe_client.upgrade_stripe_subscription_price(
                stripe_subscription_id=subscription.stripe_subscription_id,
                new_price_id=target_plan.stripe_price_id,
            )
        except Exception as exc:
            logger.exception(
                "Stripe upgrade failed for subscription %s",
                subscription.stripe_subscription_id,
            )
            raise AppException(
                code="SUBSCRIPTION_UPGRADE_FAILED",
                message="Unable to upgrade subscription at this time",
                status_code=400,
            ) from exc

    subscription.plan_id = target_plan.id
    subscription.stripe_price_id = target_plan.stripe_price_id
    subscription.pending_plan_id = None
    subscription.status = SubscriptionStatus.ACTIVE.value
    subscription.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(subscription)

    logger.info(
        "User %s upgraded subscription %s to plan %s",
        user.id,
        subscription.id,
        target_plan.id,
    )
    return await _build_subscription_response(
        db,
        subscription=subscription,
        user=user,
        message="Subscription upgraded successfully",
        description=f"Your plan is now {target_plan.name}",
    )


async def cancel_subscription(
    db: AsyncSession,
    user: User,
    payload: SubscriptionCancelRequest,
) -> dict[str, Any]:
    """Cancel the authenticated user's subscription."""
    _ = payload.full_name  # Client metadata only; ownership is enforced via JWT user.
    subscription = await _get_owned_subscription(db, user)

    if subscription.status == SubscriptionStatus.CANCELED.value:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Subscription is already canceled",
            status_code=400,
            details=[{"field": "subscription", "message": "Subscription is already canceled"}],
        )

    if stripe_client.stripe_configured():
        try:
            stripe_client.cancel_stripe_subscription(
                stripe_subscription_id=subscription.stripe_subscription_id,
                at_period_end=True,
            )
        except Exception as exc:
            logger.exception(
                "Stripe cancel failed for subscription %s",
                subscription.stripe_subscription_id,
            )
            raise AppException(
                code="SUBSCRIPTION_CANCEL_FAILED",
                message="Unable to cancel subscription at this time",
                status_code=400,
            ) from exc

    subscription.status = SubscriptionStatus.CANCELED.value
    subscription.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(subscription)

    logger.info("User %s canceled subscription %s", user.id, subscription.id)
    return await _build_subscription_response(
        db,
        subscription=subscription,
        user=user,
        message="Subscription canceled successfully",
        description="Your subscription will remain active until the current billing period ends",
    )
