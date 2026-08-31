"""Business logic for organization admin billing management."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Any

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

EXPIRY_PATTERN = re.compile(r"^(0[1-9]|1[0-2])/(\d{2})$")
ALLOWED_BILLING_STATUSES = frozenset({"paid", "pending", "failed"})
HISTORY_SUCCESS_MESSAGE = "Billing history loaded successfully."
UPDATE_SUCCESS_MESSAGE = "Payment method updated successfully."
NO_HISTORY_MESSAGE = "No billing history is available."
STRIPE_CARD_ERROR_MESSAGE = "Enter a valid card number, expiry date, and security code."

MIN_CARD_LENGTH = 13
MAX_CARD_LENGTH = 19


def _require_stripe_configured() -> None:
    """Ensure Stripe billing is available before updating payment methods."""
    if not stripe_client.stripe_configured():
        raise AppException(
            code="STRIPE_NOT_CONFIGURED",
            message="Billing is temporarily unavailable",
            status_code=503,
        )


def _luhn_valid(card_number: str) -> bool:
    """Return True when the card number passes the Luhn checksum."""
    digits = [int(digit) for digit in card_number]
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


def _parse_expiry(expiry_date: str) -> tuple[int, int]:
    """Parse MM/YY expiry and return (exp_month, exp_year)."""
    match = EXPIRY_PATTERN.match(expiry_date.strip())
    if match is None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid expiry date",
            status_code=400,
            details=[
                {
                    "field": "expiry_date",
                    "message": "Expiry date must use MM/YY format",
                }
            ],
        )
    exp_month = int(match.group(1))
    exp_year = 2000 + int(match.group(2))
    today = datetime.now(timezone.utc).date()
    if exp_year < today.year or (exp_year == today.year and exp_month < today.month):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Card has expired",
            status_code=400,
            details=[{"field": "expiry_date", "message": "Card has expired"}],
        )
    return exp_month, exp_year


def validate_payment_method_payload(payload: PaymentMethodUpdateRequest) -> tuple[str, int, int, str]:
    """Validate card fields and return normalized values for Stripe tokenization."""
    card_number = re.sub(r"\D", "", payload.card_number or "")
    if not card_number:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Card number is required",
            status_code=400,
            details=[{"field": "card_number", "message": "Card number is required"}],
        )
    if not MIN_CARD_LENGTH <= len(card_number) <= MAX_CARD_LENGTH:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid card number",
            status_code=400,
            details=[{"field": "card_number", "message": "Enter a valid card number"}],
        )
    if not _luhn_valid(card_number):
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid card number",
            status_code=400,
            details=[{"field": "card_number", "message": "Enter a valid card number"}],
        )

    expiry_raw = (payload.expiry_date or "").strip()
    if not expiry_raw:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Expiry date is required",
            status_code=400,
            details=[{"field": "expiry_date", "message": "Expiry date is required"}],
        )
    exp_month, exp_year = _parse_expiry(expiry_raw)

    cvv = re.sub(r"\D", "", payload.cvv or "")
    if not cvv:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Security code is required",
            status_code=400,
            details=[{"field": "cvv", "message": "Security code is required"}],
        )
    if len(cvv) not in {3, 4}:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Enter a valid security code",
            status_code=400,
            details=[{"field": "cvv", "message": "Security code must be 3 or 4 digits"}],
        )

    return card_number, exp_month, exp_year, cvv


def _format_expiry(exp_month: int, exp_year: int) -> str:
    """Format expiry as MM/YY for API responses."""
    return f"{exp_month:02d}/{exp_year % 100:02d}"


def _amount_to_float(amount_cents: int) -> float:
    """Convert stored cents to a major currency float."""
    return round(amount_cents / 100.0, 2)


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


async def get_billing_history(db: AsyncSession, user: User) -> dict[str, Any]:
    """Return billing history, upcoming payments, and notifications for the org admin."""
    organization = await require_admin_organization(db, user)

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

    payment_method_result = await db.execute(
        select(OrgPaymentMethod).where(OrgPaymentMethod.org_id == organization.id)
    )
    payment_method = payment_method_result.scalar_one_or_none()

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
    db: AsyncSession,
    *,
    organization: Organization,
    user: User,
    existing: OrgPaymentMethod | None,
) -> str:
    """Return the Stripe customer id for the organization."""
    if existing is not None:
        return existing.stripe_customer_id

    customer_id = stripe_client.create_stripe_customer(
        email=user.email,
        name=organization.name,
        metadata={"org_id": str(organization.id)},
    )
    return customer_id


async def update_payment_method(
    db: AsyncSession,
    user: User,
    payload: PaymentMethodUpdateRequest,
) -> dict[str, Any]:
    """Tokenize card details with Stripe and persist PCI-safe payment method metadata."""
    _require_stripe_configured()
    organization = await require_admin_organization(db, user)
    card_number, exp_month, exp_year, cvv = validate_payment_method_payload(payload)

    existing_result = await db.execute(
        select(OrgPaymentMethod).where(OrgPaymentMethod.org_id == organization.id)
    )
    existing = existing_result.scalar_one_or_none()

    try:
        stripe_customer_id = await _get_or_create_stripe_customer(
            db,
            organization=organization,
            user=user,
            existing=existing,
        )
        payment_method = stripe_client.create_card_payment_method(
            card_number=card_number,
            exp_month=exp_month,
            exp_year=exp_year,
            cvc=cvv,
        )
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
            message=STRIPE_CARD_ERROR_MESSAGE,
            status_code=400,
            details=[{"field": "card_number", "message": STRIPE_CARD_ERROR_MESSAGE}],
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

    logger.info("Org admin %s updated payment method for organization %s", user.id, organization.id)

    return {
        "success": True,
        "message": UPDATE_SUCCESS_MESSAGE,
        "data": summary,
        "error": None,
    }
