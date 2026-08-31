"""Organization admin subscription management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error
from app.schemas.org_admin_subscription import (
    OrgAdminSubscriptionResponse,
    OrgAdminSubscriptionUpgradeRequest,
)
from app.services import org_admin_subscription as org_admin_subscription_service

router = APIRouter(prefix="/admin/subscription", tags=["org-admin-subscription"])

AUTH_ERROR_RESPONSES = {
    401: openapi_error(
        "Missing, invalid, expired, or revoked JWT",
        code="MISSING_TOKEN",
        message="Could not validate credentials",
    ),
    403: openapi_error(
        "Authenticated user is not an organization admin",
        code="FORBIDDEN",
        message="You do not have permission to access this resource",
    ),
}

VALIDATION_ERROR_RESPONSES = {
    400: openapi_error(
        "Invalid subscription plan or upgrade request",
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[{"field": "full_name", "message": "Subscription plan is invalid or unavailable"}],
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

NOT_FOUND_ERROR_RESPONSE = {
    404: openapi_error(
        "No subscription exists for the organization admin account",
        code="SUBSCRIPTION_NOT_FOUND",
        message="No subscription found for this account",
    ),
}


@router.get(
    "",
    response_model=OrgAdminSubscriptionResponse,
    operation_id="getOrgAdminSubscription",
    summary="Get organization subscription details",
    description=(
        "Return the authenticated organization admin's current subscription for the "
        "**Subscription Management** screen.\n\n"
        "Includes `subscription_plan`, `features_included`, `renewal_date`, "
        "`billing_cycle`, `full_name`, and mobile envelope fields (`title`, `status`, "
        "`description`, `notification`). When renewal is within five days, a `warning` "
        "message is included.\n\n"
        "Returns **404** when no subscription record exists.\n\n"
        "**Requires organization admin JWT** (`Authorization: Bearer <access_token>`)."
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
async def get_org_subscription(
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminSubscriptionResponse:
    """Return subscription details for the Organization Admin Subscription Management screen."""
    payload = await org_admin_subscription_service.get_org_subscription(db, current_user)
    return OrgAdminSubscriptionResponse(**payload)


@router.post(
    "/upgrade",
    response_model=OrgAdminSubscriptionResponse,
    operation_id="upgradeOrgAdminSubscription",
    summary="Upgrade organization subscription plan",
    description=(
        "Upgrade the authenticated organization admin's subscription to another active "
        "org-admin plan through Stripe.\n\n"
        "Provide either `plan_id` (UUID) or `full_name` with the target plan display name "
        "from the plan-name-group field (e.g. `\"Pro Plan\"`). Stripe identifiers are "
        "resolved server-side.\n\n"
        "Returns **200** with a success `notification` on upgrade. When renewal is within "
        "five days, a `warning` message is included in the response.\n\n"
        "Returns **404** when no subscription exists. Returns **400** for invalid plan "
        "data or upgrade failures. Returns **503** when Stripe billing is not configured.\n\n"
        "**Requires organization admin JWT**."
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
async def upgrade_org_subscription(
    body: OrgAdminSubscriptionUpgradeRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> OrgAdminSubscriptionResponse:
    """Upgrade the organization subscription from the Subscription Management screen."""
    payload = await org_admin_subscription_service.upgrade_org_subscription(
        db,
        current_user,
        body,
    )
    return OrgAdminSubscriptionResponse(**payload)
