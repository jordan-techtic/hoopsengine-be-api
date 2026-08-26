from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin
from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.enums import (
    BillingFrequency,
    HistoricalRecordsDuration,
    LimitType,
    PlanStatus,
    SubscriptionPlanRole,
)
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.schemas.errors import ErrorResponse
from app.schemas.pagination import PaginationMeta
from app.schemas.subscription_plan import (
    CurrencyListResponse,
    SubscriptionPlanCreateRequest,
    SubscriptionPlanDeleteResponse,
    SubscriptionPlanItem,
    SubscriptionPlanListResponse,
    SubscriptionPlanStatusCounts,
    SubscriptionPlanUpdateRequest,
)
from app.services import stripe_client
from app.services import subscription_plan as subscription_plan_service

router = APIRouter(prefix="/admin/subscription-plans", tags=["admin-subscription-plans"])


def _stripe_status_for_plan(plan: SubscriptionPlan) -> PlanStatus | None:
    if not stripe_client.stripe_configured():
        return None
    stripe_active = stripe_client.get_stripe_catalog_active(
        product_id=plan.stripe_product_id,
        price_id=plan.stripe_price_id,
    )
    if stripe_active is None:
        return None
    return PlanStatus.ACTIVE if stripe_active else PlanStatus.ARCHIVED


def _to_item(
    plan: SubscriptionPlan,
    *,
    stripe_status: PlanStatus | None = None,
) -> SubscriptionPlanItem:
    return SubscriptionPlanItem(
        id=plan.id,
        role=SubscriptionPlanRole(plan.role),
        name=plan.name,
        billing_frequency=BillingFrequency(plan.billing_frequency),
        currency=plan.currency,
        price_amount=subscription_plan_service.cents_to_decimal(plan.price_amount_cents),
        stripe_product_id=plan.stripe_product_id,
        stripe_price_id=plan.stripe_price_id,
        teams_limit_type=LimitType(plan.teams_limit_type),
        teams_count=plan.teams_count,
        coaches_limit_type=(
            LimitType(plan.coaches_limit_type) if plan.coaches_limit_type else None
        ),
        coaches_count=plan.coaches_count,
        players_limit_type=LimitType(plan.players_limit_type),
        players_count=plan.players_count,
        historical_records_duration=HistoricalRecordsDuration(plan.historical_records_duration),
        is_active=plan.is_active,
        include_offline_sync=plan.include_offline_sync,
        status=subscription_plan_service.local_plan_status(plan),
        archived_at=plan.archived_at,
        replacement_plan_id=plan.replacement_plan_id,
        stripe_status=stripe_status if stripe_status is not None else _stripe_status_for_plan(plan),
        description=plan.description,
        features=plan.features or [],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.get(
    "/currencies",
    response_model=CurrencyListResponse,
    summary="List Stripe-supported currencies",
    description=(
        "Returns Stripe-supported currency codes for the admin plan currency dropdown.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
        503: {"model": ErrorResponse, "description": "Stripe is not configured"},
    },
)
async def list_currencies(
    _: User = Depends(get_current_super_admin),
) -> CurrencyListResponse:
    if not stripe_client.stripe_configured():
        raise AppException(
            code="STRIPE_NOT_CONFIGURED",
            message="Stripe is not configured on the server",
            status_code=503,
        )

    currencies = stripe_client.list_supported_currencies()
    return CurrencyListResponse(items=currencies)


@router.get(
    "",
    response_model=SubscriptionPlanListResponse,
    summary="List subscription plans by role",
    description=(
        "Fetch subscription plans for a specific role, split into Active and Archived categories.\n\n"
        "Use `status=active` or `status=archived` for the admin tabs. "
        "Each item includes local `status` and Stripe `stripe_status` "
        "(from the Stripe product `active` flag).\n\n"
        "Use `role=org_admin` for organization admin plans and `role=coach` for coach plans.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def list_subscription_plans(
    role: SubscriptionPlanRole = Query(
        ...,
        description="Subscription audience role: `org_admin` or `coach`",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: PlanStatus | None = Query(
        default=None,
        description="Plan category: `active` or `archived`. Omit to return both.",
    ),
    billing_frequency: BillingFrequency | None = Query(default=None),
    is_active: bool | None = Query(
        default=None,
        description="Deprecated. Prefer `status=active` or `status=archived`.",
    ),
    search: str | None = Query(default=None),
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionPlanListResponse:
    items, total, counts = await subscription_plan_service.list_plans(
        db,
        page=page,
        page_size=page_size,
        role=role,
        status=status,
        billing_frequency=billing_frequency,
        is_active=is_active,
        search=search,
    )
    meta = subscription_plan_service.build_pagination_meta(
        total=total,
        page=page,
        page_size=page_size,
    )
    return SubscriptionPlanListResponse(
        items=[_to_item(item) for item in items],
        pagination=PaginationMeta(**meta),
        counts=SubscriptionPlanStatusCounts(**counts),
    )


@router.get(
    "/{plan_id}",
    response_model=SubscriptionPlanItem,
    summary="Get subscription plan by role",
    description=(
        "Fetch a single subscription plan by ID, scoped to the given role.\n\n"
        "Returns `404` if the plan exists but belongs to a different role.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
        404: {"model": ErrorResponse, "description": "Plan not found for this role"},
    },
)
async def get_subscription_plan(
    plan_id: UUID,
    role: SubscriptionPlanRole = Query(
        ...,
        description="Subscription audience role: `org_admin` or `coach`",
    ),
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionPlanItem:
    plan = await subscription_plan_service.get_plan_by_id(db, plan_id, role=role)
    if plan is None:
        raise AppException(
            code="PLAN_NOT_FOUND",
            message="Subscription plan not found for the specified role",
            status_code=404,
        )
    return _to_item(plan)


@router.post(
    "",
    response_model=SubscriptionPlanItem,
    summary="Create subscription plan",
    description=(
        "Create a subscription plan for `org_admin` or `coach` and the corresponding "
        "Stripe product/price.\n\n"
        "Currency, billing frequency, and role are fixed after creation.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        503: {"model": ErrorResponse, "description": "Stripe is not configured"},
    },
)
async def create_subscription_plan(
    payload: SubscriptionPlanCreateRequest,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionPlanItem:
    plan = await subscription_plan_service.create_plan(
        db,
        role=payload.role,
        name=payload.name,
        billing_frequency=payload.billing_frequency,
        currency=payload.currency,
        price_amount=payload.price_amount,
        teams_limit_type=payload.teams_limit_type,
        teams_count=payload.teams_count,
        coaches_limit_type=payload.coaches_limit_type,
        coaches_count=payload.coaches_count,
        players_limit_type=payload.players_limit_type,
        players_count=payload.players_count,
        historical_records_duration=payload.historical_records_duration,
        is_active=payload.is_active,
        include_offline_sync=payload.include_offline_sync,
        description=payload.description,
        features=payload.features,
    )
    return _to_item(plan)


@router.put(
    "/{plan_id}",
    response_model=SubscriptionPlanItem,
    summary="Update subscription plan",
    description=(
        "Update a subscription plan scoped to the given role.\n\n"
        "**Immutable after creation:** `role`, `currency`, `billing_frequency`.\n\n"
        "When `price_amount` changes, the backend creates a new Stripe price, "
        "migrates active subscribers to it, and emails them about the change.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Immutable field or business rule error"},
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
        404: {"model": ErrorResponse, "description": "Plan not found for this role"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        503: {"model": ErrorResponse, "description": "Stripe is not configured"},
    },
)
async def update_subscription_plan(
    plan_id: UUID,
    payload: SubscriptionPlanUpdateRequest,
    role: SubscriptionPlanRole = Query(
        ...,
        description="Subscription audience role: `org_admin` or `coach`",
    ),
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionPlanItem:
    plan = await subscription_plan_service.get_plan_by_id(db, plan_id, role=role)
    if plan is None:
        raise AppException(
            code="PLAN_NOT_FOUND",
            message="Subscription plan not found for the specified role",
            status_code=404,
        )

    updated_plan = await subscription_plan_service.update_plan(
        db,
        plan,
        name=payload.name,
        price_amount=payload.price_amount,
        teams_limit_type=payload.teams_limit_type,
        teams_count=payload.teams_count,
        coaches_limit_type=payload.coaches_limit_type,
        coaches_count=payload.coaches_count,
        players_limit_type=payload.players_limit_type,
        players_count=payload.players_count,
        historical_records_duration=payload.historical_records_duration,
        is_active=payload.is_active,
        include_offline_sync=payload.include_offline_sync,
        description=payload.description,
        features=payload.features,
        currency=payload.currency,
        billing_frequency=payload.billing_frequency,
    )
    return _to_item(updated_plan)


@router.delete(
    "/{plan_id}",
    response_model=SubscriptionPlanDeleteResponse,
    summary="Archive subscription plan",
    description=(
        "Archive a subscription plan scoped to the given role.\n\n"
        "New customers cannot subscribe because the Stripe product/price is deactivated. "
        "Existing subscribers keep the current plan until the billing period ends, then "
        "are auto-migrated to a replacement plan when one is available.\n\n"
        "Optional query param `replacement_plan_id` selects the destination plan. "
        "If omitted, the backend uses another active plan with the same role, name, "
        "and billing frequency when one exists.\n\n"
        "Purchased users are emailed about the archive.\n\n"
        "**Requires super admin JWT**."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "User is not a super admin"},
        404: {"model": ErrorResponse, "description": "Plan not found for this role"},
        422: {"model": ErrorResponse, "description": "Invalid replacement plan"},
    },
)
async def delete_subscription_plan(
    plan_id: UUID,
    role: SubscriptionPlanRole = Query(
        ...,
        description="Subscription audience role: `org_admin` or `coach`",
    ),
    replacement_plan_id: UUID | None = Query(
        default=None,
        description="Optional active plan to migrate existing subscribers to at period end",
    ),
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionPlanDeleteResponse:
    plan = await subscription_plan_service.get_plan_by_id(db, plan_id, role=role)
    if plan is None:
        raise AppException(
            code="PLAN_NOT_FOUND",
            message="Subscription plan not found for the specified role",
            status_code=404,
        )

    await subscription_plan_service.archive_plan(
        db,
        plan,
        replacement_plan_id=replacement_plan_id,
    )
    return SubscriptionPlanDeleteResponse(message="Subscription plan archived successfully.")
