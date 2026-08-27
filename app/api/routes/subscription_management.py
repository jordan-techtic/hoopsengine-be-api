"""Coach subscription management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_authenticated_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.subscription_management import (
    SubscriptionCancelRequest,
    SubscriptionDetailsResponse,
    SubscriptionUpgradeRequest,
)
from app.services import subscription_management as subscription_management_service

router = APIRouter(prefix="/subscription", tags=["subscription-management"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "User is not allowed to manage this subscription",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Invalid subscription action or plan data",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "plan_id", "message": "Subscription plan is invalid or unavailable"}],
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "No subscription exists for the authenticated user",
        code="SUBSCRIPTION_NOT_FOUND",
        message="No subscription found for this account",
    ),
}


@router.get(
    "",
    response_model=SubscriptionDetailsResponse,
    operation_id="getCurrentSubscription",
    summary="Get current subscription details",
    description=(
        "Return the authenticated user's current subscription for the "
        "**subscription-management** screen.\n\n"
        "Includes `current_plan`, `expiry_date`, `features`, `full_name`, and the "
        "mobile envelope fields `title`, `status`, `description`, and `name`.\n\n"
        "Returns **404** when no subscription record exists for the user.\n\n"
        "**Requires authenticated JWT** (`Authorization: Bearer <access_token>`)."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_current_subscription(
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionDetailsResponse:
    result = await subscription_management_service.get_current_subscription(db, current_user)
    return SubscriptionDetailsResponse(**result)


@router.post(
    "/upgrade",
    response_model=SubscriptionDetailsResponse,
    operation_id="upgradeSubscription",
    summary="Upgrade subscription plan",
    description=(
        "Upgrade the authenticated user's subscription to another active plan through Stripe.\n\n"
        "Provide either `plan_id` (UUID) or `full_name` with the target plan display name "
        "from the plan-name-group field (e.g. `\"Pro Plan\"`). Stripe customer, subscription, "
        "and price identifiers are resolved server-side and must not be sent by the client.\n\n"
        "Only the subscription owner may upgrade. Returns **404** when the user has no "
        "subscription. Returns **400** for invalid or unavailable plan data. Returns **503** "
        "when Stripe billing is not configured.\n\n"
        "**Requires authenticated JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Stripe is not configured",
            code="STRIPE_NOT_CONFIGURED",
            message="Subscription billing is temporarily unavailable",
        ),
    },
)
async def upgrade_subscription(
    body: SubscriptionUpgradeRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionDetailsResponse:
    result = await subscription_management_service.upgrade_subscription(
        db,
        current_user,
        body,
    )
    return SubscriptionDetailsResponse(**result)


@router.post(
    "/cancel",
    response_model=SubscriptionDetailsResponse,
    operation_id="cancelSubscription",
    summary="Cancel subscription",
    description=(
        "Cancel the authenticated user's current subscription.\n\n"
        "Optional `full_name` is client metadata from the plan-name-group field and is "
        "not persisted. The mobile client should confirm cancellation before calling "
        "this endpoint.\n\n"
        "Returns **200** with updated subscription details on success. Returns **404** "
        "when no subscription exists. Returns **400** when the subscription is already "
        "canceled. Returns **503** when Stripe billing is not configured.\n\n"
        "**Requires authenticated JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_ERROR_RESPONSE,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
        503: openapi_error(
            "Stripe is not configured",
            code="STRIPE_NOT_CONFIGURED",
            message="Subscription billing is temporarily unavailable",
        ),
    },
)
async def cancel_subscription(
    body: SubscriptionCancelRequest,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionDetailsResponse:
    result = await subscription_management_service.cancel_subscription(
        db,
        current_user,
        body,
    )
    return SubscriptionDetailsResponse(**result)
