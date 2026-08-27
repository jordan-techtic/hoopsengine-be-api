import logging

from fastapi import APIRouter, Body, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
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


class StripeWebhookResponse(BaseModel):
    """Acknowledgement payload returned to Stripe after webhook processing."""

    model_config = ConfigDict(json_schema_extra={"example": {"status": "ok"}})

    status: str = Field(description="Processing result", examples=["ok"])


WEBHOOK_ERROR_RESPONSES = {
    400: openapi_error(
        "Missing Stripe-Signature header or invalid webhook signature",
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
    response_model=StripeWebhookResponse,
    operation_id="handleStripeWebhook",
    summary="Stripe webhook handler",
    description=(
        "Receives Stripe webhook events for subscription lifecycle sync.\n\n"
        "Send the **raw JSON event body** exactly as Stripe delivers it; the "
        "`Stripe-Signature` header is required for verification.\n\n"
        "Processes `customer.subscription.created`, `customer.subscription.updated`, "
        "`customer.subscription.deleted`, `invoice.paid`, and `invoice.payment_failed`. "
        "Duplicate deliveries are ignored using stored Stripe event IDs.\n\n"
        "Configure this URL in the Stripe Dashboard. "
        "**Public endpoint** — no JWT; authenticated via Stripe signature only."
    ),
    responses={
        **WEBHOOK_ERROR_RESPONSES,
        200: {
            "description": "Webhook accepted and processed (or skipped as duplicate)",
            "model": StripeWebhookResponse,
            "content": {
                "application/json": {
                    "example": {"status": "ok"},
                }
            },
        },
    },
)
async def stripe_webhook(
    payload: bytes = Body(
        ...,
        description="Raw Stripe event JSON bytes (must not be parsed before signature verification)",
        media_type="application/json",
    ),
    stripe_signature: str | None = Header(
        default=None,
        alias="Stripe-Signature",
        description="Stripe webhook signature header",
        examples=["t=1492774577,v1=5257a869e7ecebeb922ff1d874ba6e7932231085,v0=..."],
    ),
    db: AsyncSession = Depends(get_db),
) -> StripeWebhookResponse:
    if not stripe_signature:
        raise AppException(
            code="MISSING_STRIPE_SIGNATURE",
            message="Missing Stripe-Signature header",
            status_code=400,
        )

    try:
        event = stripe_client.construct_webhook_event(payload, stripe_signature)
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
        return StripeWebhookResponse(status="ok")

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
    return StripeWebhookResponse(status="ok")
