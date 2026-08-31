"""Business logic for organization admin subscription management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.org_admin_subscription import OrgAdminSubscriptionUpgradeRequest
from app.schemas.subscription_management import SubscriptionUpgradeRequest
from app.services import subscription_management as subscription_management_service
from app.services.org_admin_profile import require_admin_organization

logger = logging.getLogger(__name__)

RENEWAL_WARNING_DAYS = 5
RENEWAL_WARNING_MESSAGE = (
    "Your subscription renews within 5 days. Review billing details before upgrading."
)
UPGRADE_SUCCESS_NOTIFICATION = "Subscription upgraded successfully"


def _renewal_warning(expiry_dt: datetime, *, now: datetime | None = None) -> str | None:
    """Return a warning message when renewal is within five days."""
    reference = now or datetime.now(timezone.utc)
    if expiry_dt.tzinfo is None:
        expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
    days_until_renewal = (expiry_dt.date() - reference.date()).days
    if 0 <= days_until_renewal <= RENEWAL_WARNING_DAYS:
        return RENEWAL_WARNING_MESSAGE
    return None


def _renewal_date_iso(expiry_dt: datetime) -> str:
    """Format renewal date for org-admin subscription responses."""
    if expiry_dt.tzinfo is None:
        expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
    return expiry_dt.date().isoformat()


async def _build_org_admin_subscription_response(
    db: AsyncSession,
    *,
    user: User,
    base_payload: dict[str, Any],
    notification: str | None = None,
    warning: str | None = None,
) -> dict[str, Any]:
    """Map coach subscription payloads to org-admin subscription contract fields."""
    subscription = await subscription_management_service._get_owned_subscription(db, user)
    plan = await subscription_management_service._load_plan(db, subscription.plan_id)
    expiry_dt = await subscription_management_service._resolve_expiry_date(subscription)
    resolved_warning = warning if warning is not None else _renewal_warning(expiry_dt)
    plan_name = str(base_payload.get("current_plan") or plan.name)
    message = str(base_payload.get("message") or "Subscription details loaded successfully")
    description = base_payload.get("description")
    if resolved_warning and not description:
        description = resolved_warning

    return {
        "success": True,
        "message": message,
        "status": str(base_payload.get("status") or subscription.status),
        "description": description,
        "link": None,
        "error": None,
        "id": base_payload["id"],
        "title": "Subscription Management",
        "name": plan_name,
        "subscription_plan": plan_name,
        "features_included": list(base_payload.get("features") or []),
        "renewal_date": _renewal_date_iso(expiry_dt),
        "billing_cycle": plan.billing_frequency,
        "full_name": str(base_payload.get("full_name") or subscription_management_service._user_full_name(user)),
        "warning": resolved_warning,
        "notification": notification or message,
    }


async def get_org_subscription(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return the organization admin's current subscription details."""
    await require_admin_organization(db, user)
    base_payload = await subscription_management_service.get_current_subscription(db, user)
    return await _build_org_admin_subscription_response(
        db,
        user=user,
        base_payload=base_payload,
        notification=str(base_payload.get("message") or "Subscription details loaded successfully"),
    )


async def upgrade_org_subscription(
    db: AsyncSession,
    user: User,
    payload: OrgAdminSubscriptionUpgradeRequest,
) -> dict[str, Any]:
    """Upgrade the organization admin's subscription plan."""
    organization = await require_admin_organization(db, user)

    subscription = await subscription_management_service._get_owned_subscription(db, user)
    expiry_dt = await subscription_management_service._resolve_expiry_date(subscription)
    renewal_warning = _renewal_warning(expiry_dt)

    upgrade_payload = SubscriptionUpgradeRequest(
        plan_id=payload.plan_id,
        full_name=payload.full_name,
    )
    base_payload = await subscription_management_service.upgrade_subscription(
        db,
        user,
        upgrade_payload,
    )

    logger.info(
        "Org admin %s upgraded organization %s subscription %s",
        user.id,
        organization.id,
        subscription.id,
    )
    return await _build_org_admin_subscription_response(
        db,
        user=user,
        base_payload=base_payload,
        notification=UPGRADE_SUCCESS_NOTIFICATION,
        warning=renewal_warning,
    )
