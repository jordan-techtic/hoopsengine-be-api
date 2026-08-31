"""Business logic for organization admin billing management."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.org_billing import OrgBillingHistory, OrgPaymentMethod
from app.models.organization import Organization
from app.models.user import User
from app.schemas.org_billing import PaymentMethodUpdateRequest
from app.services import stripe_client
from app.services.org_admin_profile import require_admin_organization

logger = logging.getLogger(__name__)

ALLOWED_BILLING_STATUSES = frozenset({"paid", "pending", "failed"})
HISTORY_SUCCESS_MESSAGE = "Billing history loaded successfully."
UPDATE_SUCCESS_MESSAGE = "Payment method updated successfully."
NO_HISTORY_MESSAGE = "No billing history is available."
PAYMENT_METHOD_INVALID_MESSAGE = "Enter a valid payment method."
STRIPE_INVOICE_PREFIX = "stripe_invoice:"


def _require_stripe_configured() -> None:
    """Ensure Stripe billing is available before Stripe-backed operations."""
    if not stripe_client.stripe_configured():
        raise AppException(
            code="STRIPE_NOT_CONFIGURED",
            message="Billing is temporarily unavailable",
            status_code=503,
        )


def validate_stripe_payment_method_id(payment_method_id: str | None) -> str:
    """Validate a client-tokenized Stripe PaymentMethod id."""
    cleaned = (payment_method_id or "").strip()
    if not cleaned:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Payment method is required",
            status_code=400,
            details=[
                {
                    "field": "stripe_payment_method_id",
                    "message": "Payment method is required",
                }
            ],
        )
    if not cleaned.startswith("pm_"):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid payment method",
            status_code=400,
            details=[
                {
                    "field": "stripe_payment_method_id",
                    "message": "Payment method id must start with pm_",
                }
            ],
        )
    return cleaned


def _format_expiry(exp_month: int, exp_year: int) -> str:
    """Format expiry as MM/YY for API responses."""
    return f"{exp_month:02d}/{exp_year % 100:02d}"


def _amount_to_float(amount_cents: int) -> float:
    """Convert stored cents to a major currency float."""
    return round(amount_cents / 100.0, 2)


def _map_stripe_invoice_status(stripe_status: str) -> str:
    """Map Stripe invoice status to API billing status."""
    normalized = stripe_status.strip().lower()
    if normalized == "paid":
        return "paid"
    if normalized in {"open", "draft"}:
        return "pending"
    if normalized in {"uncollectible", "void"}:
        return "failed"
    return "pending"


def _history_item(row: OrgBillingHistory) -> dict[str, Any]:
    """Map a billing history row to the API item schema."""
    status = row.status if row.status in ALLOWED_BILLING_STATUSES else "paid"
    return {
        "date": row.billing_date.isoformat(),
        "amount": _amount_to_float(row.amount_cents),
        "status": status,
    }


def _payment_method_summary(method: OrgPaymentMethod) -> dict[str, Any]:
    """Map stored payment method metadata to a masked API summary."""
    return {
        "card_last4": method.card_last4,
        "expiry_date": _format_expiry(method.exp_month, method.exp_year),
        "brand": method.brand,
    }


def _build_notifications(upcoming: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build payment reminder notifications from upcoming charges."""
    notifications: list[dict[str, str]] = []
    for item in upcoming:
        notifications.append(
            {
                "type": "upcoming_payment",
                "message": (
                    f"Upcoming payment of ${item['amount']:.2f} is due on {item['date']}"
                ),
                "due_date": item["date"],
            }
        )
    return notifications


async def _sync_billing_history_from_stripe(
    db: AsyncSession,
    *,
    org_id: UUID,
    customer_id: str,
) -> None:
    """Sync billing history rows from Stripe invoices for the organization customer."""
    if not stripe_client.stripe_configured():
        return
    try:
        invoices = stripe_client.list_customer_invoices(customer_id=customer_id)
    except Exception:
        logger.exception("Failed to sync Stripe invoices for org %s", org_id)
        return

    for invoice in invoices:
        invoice_id = str(invoice["id"])
        marker = f"{STRIPE_INVOICE_PREFIX}{invoice_id}"
        existing = await db.execute(
            select(OrgBillingHistory.id).where(
                OrgBillingHistory.org_id == org_id,
                OrgBillingHistory.description == marker,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        status = _map_stripe_invoice_status(str(invoice["status"]))
        amount_cents = (
            int(invoice["amount_paid"])
            if status == "paid"
            else int(invoice["amount_due"])
        )
        created_ts = int(invoice["created"])
        billing_date = datetime.fromtimestamp(created_ts, tz=timezone.utc).date()
        db.add(
            OrgBillingHistory(
                org_id=org_id,
                billing_date=billing_date,
                amount_cents=amount_cents,
                currency=str(invoice.get("currency") or "USD"),
                status=status,
                description=marker,
            )
        )

    await db.commit()


async def get_billing_history(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return billing history, upcoming payments, and notifications for the org admin."""
    organization = await require_admin_organization(db, user)

    payment_method_result = await db.execute(
        select(OrgPaymentMethod).where(OrgPaymentMethod.org_id == organization.id)
    )
    payment_method = payment_method_result.scalar_one_or_none()
    if payment_method is not None:
        await _sync_billing_history_from_stripe(
            db,
            org_id=organization.id,
            customer_id=payment_method.stripe_customer_id,
        )

    result = await db.execute(
        select(OrgBillingHistory)
        .where(OrgBillingHistory.org_id == organization.id)
        .order_by(OrgBillingHistory.billing_date.desc())
    )
    rows = result.scalars().all()
    if not rows:
        raise AppException(
            code="BILLING_HISTORY_NOT_FOUND",
            message=NO_HISTORY_MESSAGE,
            status_code=404,
        )

    history_items = [_history_item(row) for row in rows if row.status != "pending"]
    upcoming_items = [_history_item(row) for row in rows if row.status == "pending"]

    return {
        "success": True,
        "message": HISTORY_SUCCESS_MESSAGE,
        "data": {
            "billing_history": history_items,
            "upcoming_payments": upcoming_items,
            "payment_method": (
                _payment_method_summary(payment_method) if payment_method is not None else None
            ),
            "notifications": _build_notifications(upcoming_items),
        },
        "error": None,
    }


async def _get_or_create_stripe_customer(
    *,
    organization: Organization,
    user: User,
    existing: OrgPaymentMethod | None,
) -> str:
    """Return the Stripe customer id for the organization."""
    if existing is not None:
        return existing.stripe_customer_id

    return stripe_client.create_stripe_customer(
        email=user.email,
        name=organization.name,
        metadata={"org_id": str(organization.id)},
    )


async def update_payment_method(
    db: AsyncSession,
    user: User,
    payload: PaymentMethodUpdateRequest,
) -> dict[str, Any]:
    """Attach a client-tokenized Stripe PaymentMethod and persist masked metadata."""
    _require_stripe_configured()
    organization = await require_admin_organization(db, user)
    stripe_payment_method_id = validate_stripe_payment_method_id(payload.stripe_payment_method_id)

    existing_result = await db.execute(
        select(OrgPaymentMethod).where(OrgPaymentMethod.org_id == organization.id)
    )
    existing = existing_result.scalar_one_or_none()

    try:
        stripe_customer_id = await _get_or_create_stripe_customer(
            organization=organization,
            user=user,
            existing=existing,
        )
        payment_method = stripe_client.retrieve_payment_method_metadata(stripe_payment_method_id)
        stripe_client.attach_payment_method_to_customer(
            customer_id=stripe_customer_id,
            payment_method_id=str(payment_method["id"]),
        )
    except AppException:
        raise
    except Exception as exc:
        logger.exception("Stripe payment method update failed for org %s", organization.id)
        raise AppException(
            code="PAYMENT_METHOD_INVALID",
            message=PAYMENT_METHOD_INVALID_MESSAGE,
            status_code=400,
            details=[
                {
                    "field": "stripe_payment_method_id",
                    "message": PAYMENT_METHOD_INVALID_MESSAGE,
                }
            ],
        ) from exc

    summary = {
        "card_last4": str(payment_method["last4"]),
        "expiry_date": _format_expiry(int(payment_method["exp_month"]), int(payment_method["exp_year"])),
        "brand": str(payment_method.get("brand") or "card"),
    }

    if existing is None:
        db.add(
            OrgPaymentMethod(
                org_id=organization.id,
                stripe_customer_id=stripe_customer_id,
                stripe_payment_method_id=str(payment_method["id"]),
                card_last4=summary["card_last4"],
                exp_month=int(payment_method["exp_month"]),
                exp_year=int(payment_method["exp_year"]),
                brand=summary["brand"],
            )
        )
    else:
        existing.stripe_customer_id = stripe_customer_id
        existing.stripe_payment_method_id = str(payment_method["id"])
        existing.card_last4 = summary["card_last4"]
        existing.exp_month = int(payment_method["exp_month"])
        existing.exp_year = int(payment_method["exp_year"])
        existing.brand = summary["brand"]

    await db.commit()
    await _sync_billing_history_from_stripe(
        db,
        org_id=organization.id,
        customer_id=stripe_customer_id,
    )

    logger.info("Org admin %s updated payment method for organization %s", user.id, organization.id)

    return {
        "success": True,
        "message": UPDATE_SUCCESS_MESSAGE,
        "data": summary,
        "error": None,
    }
