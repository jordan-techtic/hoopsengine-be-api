import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.schemas.errors import openapi_error
from app.services import stripe_client
from app.services.stripe_webhook import (
    is_webhook_event_processed,
    mark_webhook_event_processed,
    sync_subscription_from_stripe,
    sync_subscription_status_from_invoice,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


WEBHOOK_ERROR_RESPONSES = {
    400: openapi_error(
        "Missing or invalid Stripe-Signature header",
        code="INVALID_STRIPE_SIGNATURE",
        message="Invalid Stripe webhook signature",
    ),
    500: openapi_error(
        "Unexpected server error while processing webhook",
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
    ),
}


@router.post(
    "/stripe",
    summary="Stripe webhook handler",
    description=(
        "Receives Stripe webhook events for subscription lifecycle sync.\n\n"
        "Processes `customer.subscription.created`, `customer.subscription.updated`, "
        "`customer.subscription.deleted`, `invoice.paid`, and `invoice.payment_failed`. "
        "Duplicate deliveries are ignored using stored Stripe event IDs.\n\n"
        "Configure this URL in the Stripe Dashboard. "
        "No JWT authentication — verified via the Stripe-Signature header."
    ),
    responses={
        **WEBHOOK_ERROR_RESPONSES,
        200: {
            "description": "Webhook accepted and processed (or skipped as duplicate)",
            "content": {
                "application/json": {
                    "example": {"status": "ok"},
                }
            },
        },
    },
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

    event_id = event["id"]
    event_type = event["type"]
    data_object = event["data"]["object"]

    if await is_webhook_event_processed(db, event_id):
        logger.info("Skipping duplicate Stripe webhook event %s", event_id)
        return {"status": "ok"}

    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        await sync_subscription_from_stripe(db, stripe_subscription=data_object)
    elif event_type == "invoice.paid":
        await sync_subscription_status_from_invoice(db, invoice=data_object)
    elif event_type == "invoice.payment_failed":
        subscription_id = data_object.get("subscription")
        if subscription_id:
            logger.info("Stripe invoice payment failed for subscription %s", subscription_id)

    await mark_webhook_event_processed(
        db,
        stripe_event_id=event_id,
        event_type=event_type,
    )
    return {"status": "ok"}
