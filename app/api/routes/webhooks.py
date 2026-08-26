import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.services import stripe_client
from app.services.stripe_webhook import sync_subscription_from_stripe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/stripe",
    summary="Stripe webhook handler",
    description=(
        "Receives Stripe webhook events for subscription lifecycle sync.\n\n"
        "Configure this URL in the Stripe Dashboard. "
        "No JWT authentication — verified via Stripe signature."
    ),
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise AppException(
            code="MISSING_STRIPE_SIGNATURE",
            message="Missing Stripe-Signature header",
            status_code=400,
        )

    try:
        event = stripe_client.construct_webhook_event(payload, signature)
    except Exception as exc:
        logger.warning("Invalid Stripe webhook signature: %s", exc)
        raise AppException(
            code="INVALID_STRIPE_SIGNATURE",
            message="Invalid Stripe webhook signature",
            status_code=400,
        ) from exc

    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        await sync_subscription_from_stripe(db, stripe_subscription=data_object)
    elif event_type == "invoice.payment_failed":
        subscription_id = data_object.get("subscription")
        if subscription_id:
            logger.info("Stripe invoice payment failed for subscription %s", subscription_id)

    return {"status": "ok"}
