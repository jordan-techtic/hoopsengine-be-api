"""Organization admin billing management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_org_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.errors import openapi_error, openapi_error_examples
from app.schemas.org_billing import (
    BillingHistoryResponse,
    PaymentMethodUpdateRequest,
    PaymentMethodUpdateResponse,
)
from app.services import org_billing as org_billing_service

router = APIRouter(prefix="/admin/billing", tags=["org-admin-billing"])
billing_alias_router = APIRouter(prefix="/billing", tags=["org-admin-billing-alias"])

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
    400: openapi_error_examples(
        "Missing or invalid Stripe payment method token",
        examples={
            "missing_payment_method": {
                "code": "VALIDATION_ERROR",
                "message": "Payment method is required",
                "details": [
                    {
                        "field": "stripe_payment_method_id",
                        "message": "Payment method is required",
                    }
                ],
            },
            "invalid_payment_method": {
                "code": "PAYMENT_METHOD_INVALID",
                "message": "Enter a valid payment method",
                "details": [
                    {
                        "field": "stripe_payment_method_id",
                        "message": "Enter a valid payment method",
                    }
                ],
            },
        },
    ),
    422: openapi_error(
        "Request body failed schema validation",
        code="VALIDATION_ERROR",
        message="Request validation failed",
    ),
}

NOT_FOUND_RESPONSES = {
    404: openapi_error_examples(
        "Organization profile or billing history not found",
        examples={
            "organization_not_found": {
                "code": "ORGANIZATION_NOT_FOUND",
                "message": "Organization profile not found",
                "details": None,
            },
            "billing_history_not_found": {
                "code": "BILLING_HISTORY_NOT_FOUND",
                "message": "No billing history is available.",
                "details": None,
            },
        },
    ),
}


@router.get(
    "/history",
    response_model=BillingHistoryResponse,
    operation_id="getOrgAdminBillingHistory",
    summary="Get organization billing history",
    description=(
        "Retrieve billing history, upcoming payments, payment notifications, and the masked "
        "payment method on file for the authenticated organization admin.\n\n"
        "Returns **200** with `billing_history`, `upcoming_payments`, `notifications`, and "
        "`payment_method`.\n\n"
        "Returns **404** when no billing history exists for the organization.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_admin_billing_history(
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> BillingHistoryResponse:
    """Return billing history and upcoming payment notifications."""
    payload = await org_billing_service.get_billing_history(db, current_user)
    return BillingHistoryResponse(**payload)


@router.post(
    "/payment-method",
    response_model=PaymentMethodUpdateResponse,
    status_code=status.HTTP_200_OK,
    operation_id="updateOrgAdminPaymentMethod",
    summary="Update organization payment method",
    description=(
        "Update the organization payment method using a **client-tokenized** Stripe PaymentMethod.\n\n"
        "**Required body field:** `stripe_payment_method_id` (created via Stripe.js / Payment Element).\n\n"
        "Raw card numbers and CVV values must **never** be sent to this API.\n\n"
        "Returns **200** with a success message and masked card metadata. Returns **400** when the "
        "token is missing or invalid. Returns **503** when Stripe billing is unavailable.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        503: openapi_error(
            "Stripe billing is not configured",
            code="STRIPE_NOT_CONFIGURED",
            message="Billing is temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def update_admin_payment_method(
    body: PaymentMethodUpdateRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> PaymentMethodUpdateResponse:
    """Update the organization payment method."""
    payload = await org_billing_service.update_payment_method(db, current_user, body)
    return PaymentMethodUpdateResponse(**payload)


@billing_alias_router.get(
    "/history",
    response_model=BillingHistoryResponse,
    operation_id="getBillingHistoryAlias",
    summary="Get billing history (alias path)",
    description=(
        "Ticket-path alias for **GET /api/v1/admin/billing/history**.\n\n"
        "Retrieve billing history and upcoming payment notifications.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def get_billing_history_alias(
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> BillingHistoryResponse:
    """Return billing history via the billing alias path."""
    payload = await org_billing_service.get_billing_history(db, current_user)
    return BillingHistoryResponse(**payload)


@billing_alias_router.put(
    "/payment-method",
    response_model=PaymentMethodUpdateResponse,
    operation_id="updatePaymentMethodAlias",
    summary="Update payment method (alias path)",
    description=(
        "Ticket-path alias for payment method updates using **PUT**.\n\n"
        "Accepts the same request body and validation rules as "
        "**POST /api/v1/admin/billing/payment-method**.\n\n"
        "**Requires organization admin JWT**."
    ),
    responses={
        **AUTH_ERROR_RESPONSES,
        **VALIDATION_ERROR_RESPONSES,
        **NOT_FOUND_RESPONSES,
        503: openapi_error(
            "Stripe billing is not configured",
            code="STRIPE_NOT_CONFIGURED",
            message="Billing is temporarily unavailable",
        ),
        500: openapi_error(
            "Unexpected server error",
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
        ),
    },
)
async def update_payment_method_alias(
    body: PaymentMethodUpdateRequest,
    current_user: User = Depends(get_current_org_admin),
    db: AsyncSession = Depends(get_db),
) -> PaymentMethodUpdateResponse:
    """Update payment method via the billing alias path."""
    payload = await org_billing_service.update_payment_method(db, current_user, body)
    return PaymentMethodUpdateResponse(**payload)
