import logging

import stripe

from app.core.config import settings

logger = logging.getLogger(__name__)

# Common Stripe billing currencies for admin plan creation.
DEFAULT_STRIPE_CURRENCIES = (
    "USD",
    "EUR",
    "GBP",
    "CAD",
    "AUD",
    "INR",
    "JPY",
    "CHF",
    "SEK",
    "NOK",
    "DKK",
    "SGD",
    "HKD",
    "NZD",
    "MXN",
    "BRL",
    "AED",
    "SAR",
)


def stripe_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def get_stripe_client() -> stripe.StripeClient:
    if not stripe_configured():
        raise RuntimeError("Stripe is not configured")
    return stripe.StripeClient(settings.STRIPE_SECRET_KEY)


def list_supported_currencies() -> list[dict[str, str]]:
    """Return Stripe-supported currencies for admin dropdown."""
    currencies: set[str] = set(DEFAULT_STRIPE_CURRENCIES)

    if stripe_configured():
        try:
            client = get_stripe_client()
            page = client.country_specs.list()
            for spec in page.data:
                currencies.update(spec.supported_payment_currencies)
            while page.has_more:
                page = client.country_specs.list(
                    params={"starting_after": page.data[-1].id}
                )
                for spec in page.data:
                    currencies.update(spec.supported_payment_currencies)
        except Exception:
            logger.exception(
                "Failed to fetch Stripe country specs; using default currency list"
            )

    return [
        {"code": code.upper(), "name": code.upper()}
        for code in sorted(currencies)
    ]


def create_stripe_product(*, name: str, description: str | None, metadata: dict[str, str]) -> str:
    client = get_stripe_client()
    product = client.products.create(
        params={
            "name": name,
            "description": description or None,
            "metadata": metadata,
        }
    )
    return product.id


def create_stripe_price(
    *,
    product_id: str,
    currency: str,
    unit_amount_cents: int,
    billing_frequency: str,
) -> str:
    client = get_stripe_client()
    interval = "month" if billing_frequency == "monthly" else "year"
    price = client.prices.create(
        params={
            "product": product_id,
            "currency": currency.lower(),
            "unit_amount": unit_amount_cents,
            "recurring": {"interval": interval},
        }
    )
    return price.id


def archive_stripe_price(price_id: str) -> None:
    client = get_stripe_client()
    client.prices.update(price_id, params={"active": False})


def archive_stripe_product(product_id: str) -> None:
    client = get_stripe_client()
    client.products.update(product_id, params={"active": False})


def migrate_subscription_to_new_price(
    *,
    stripe_subscription_id: str,
    new_price_id: str,
) -> None:
    client = get_stripe_client()
    subscription = client.subscriptions.retrieve(stripe_subscription_id)
    if not subscription.items or not subscription.items.data:
        logger.warning(
            "Stripe subscription %s has no items; skipping migration",
            stripe_subscription_id,
        )
        return

    item_id = subscription.items.data[0].id
    client.subscriptions.update(
        stripe_subscription_id,
        params={
            "items": [{"id": item_id, "price": new_price_id}],
            "proration_behavior": settings.STRIPE_PRICE_MIGRATION_PRORATION_BEHAVIOR,
        },
    )


def _stripe_value(obj: object, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def get_subscription_current_period_end(stripe_subscription_id: str) -> int | None:
    client = get_stripe_client()
    subscription = client.subscriptions.retrieve(stripe_subscription_id)
    period_end = _stripe_value(subscription, "current_period_end")
    if period_end:
        return int(period_end)

    items = _stripe_value(subscription, "items")
    item_data = _stripe_value(items, "data") or []
    if item_data:
        item_period_end = _stripe_value(item_data[0], "current_period_end")
        if item_period_end:
            return int(item_period_end)
    return None


def schedule_subscription_price_change_at_period_end(
    *,
    stripe_subscription_id: str,
    new_price_id: str,
) -> int | None:
    """Keep the current price until period end, then switch to the new price."""
    client = get_stripe_client()
    subscription = client.subscriptions.retrieve(stripe_subscription_id)
    items = _stripe_value(subscription, "items")
    item_data = _stripe_value(items, "data") or []
    if not item_data:
        logger.warning(
            "Stripe subscription %s has no items; skipping period-end migration",
            stripe_subscription_id,
        )
        return None

    current_price_obj = _stripe_value(item_data[0], "price")
    current_price = (
        current_price_obj
        if isinstance(current_price_obj, str)
        else _stripe_value(current_price_obj, "id")
    )

    period_end = _stripe_value(subscription, "current_period_end")
    if not period_end:
        period_end = _stripe_value(item_data[0], "current_period_end")
    if not period_end:
        logger.warning(
            "Stripe subscription %s has no current_period_end; skipping period-end migration",
            stripe_subscription_id,
        )
        return None

    existing_schedule = _stripe_value(subscription, "schedule")
    if existing_schedule:
        schedule_id = (
            existing_schedule
            if isinstance(existing_schedule, str)
            else _stripe_value(existing_schedule, "id")
        )
        schedule = client.subscription_schedules.retrieve(schedule_id)
    else:
        schedule = client.subscription_schedules.create(
            params={"from_subscription": stripe_subscription_id}
        )

    phases = _stripe_value(schedule, "phases") or []
    start_date = _stripe_value(phases[0], "start_date") if phases else "now"
    quantity = _stripe_value(item_data[0], "quantity") or 1

    client.subscription_schedules.update(
        schedule.id,
        params={
            "end_behavior": "release",
            "phases": [
                {
                    "items": [{"price": current_price, "quantity": quantity}],
                    "start_date": start_date,
                    "end_date": int(period_end),
                },
                {
                    "items": [{"price": new_price_id, "quantity": quantity}],
                },
            ],
        },
    )
    return int(period_end)


def get_stripe_product_active(product_id: str) -> bool | None:
    try:
        client = get_stripe_client()
        product = client.products.retrieve(product_id)
        active = _stripe_value(product, "active")
        if active is None:
            return None
        return bool(active)
    except Exception:
        logger.exception("Failed to retrieve Stripe product %s", product_id)
        return None


def get_stripe_price_active(price_id: str) -> bool | None:
    try:
        client = get_stripe_client()
        price = client.prices.retrieve(price_id)
        active = _stripe_value(price, "active")
        if active is None:
            return None
        return bool(active)
    except Exception:
        logger.exception("Failed to retrieve Stripe price %s", price_id)
        return None


def get_stripe_catalog_active(*, product_id: str, price_id: str) -> bool | None:
    product_active = get_stripe_product_active(product_id)
    price_active = get_stripe_price_active(price_id)
    if product_active is None and price_active is None:
        return None
    if product_active is False or price_active is False:
        return False
    if product_active is True and price_active is True:
        return True
    return None


def cancel_stripe_subscription(
    *,
    stripe_subscription_id: str,
    at_period_end: bool = True,
) -> None:
    """Cancel a Stripe subscription immediately or at period end."""
    client = get_stripe_client()
    if at_period_end:
        client.subscriptions.update(
            stripe_subscription_id,
            params={"cancel_at_period_end": True},
        )
        return
    client.subscriptions.cancel(stripe_subscription_id)


def upgrade_stripe_subscription_price(
    *,
    stripe_subscription_id: str,
    new_price_id: str,
) -> None:
    """Switch an existing Stripe subscription to a new price."""
    migrate_subscription_to_new_price(
        stripe_subscription_id=stripe_subscription_id,
        new_price_id=new_price_id,
    )


def construct_webhook_event(payload: bytes, signature: str) -> stripe.Event:
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("Stripe webhook secret is not configured")
    return stripe.Webhook.construct_event(
        payload,
        signature,
        settings.STRIPE_WEBHOOK_SECRET,
    )
