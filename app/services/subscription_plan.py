import logging
import math
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import (
    send_subscription_plan_archived_email,
    send_subscription_price_change_email,
)
from app.core.exceptions import AppException
from app.models.enums import (
    BillingFrequency,
    HistoricalRecordsDuration,
    LimitType,
    PlanStatus,
    SubscriptionPlanRole,
    SubscriptionStatus,
)
from app.models.subscription import StripeSubscription
from app.models.subscription_plan import SubscriptionPlan
from app.services import stripe_client

logger = logging.getLogger(__name__)

ACTIVE_SUBSCRIPTION_STATUSES = {
    SubscriptionStatus.ACTIVE.value,
    SubscriptionStatus.TRIALING.value,
    SubscriptionStatus.PAST_DUE.value,
}


def cents_to_decimal(amount_cents: int) -> Decimal:
    return (Decimal(amount_cents) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decimal_to_cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def format_price(amount_cents: int, currency: str) -> str:
    return f"{currency.upper()} {cents_to_decimal(amount_cents)}"


def _validate_limit_fields(
    *,
    limit_type: LimitType,
    count: int | None,
    field_label: str,
) -> None:
    if limit_type == LimitType.LIMITED and (count is None or count < 1):
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{field_label} count is required when limit type is limited",
            status_code=422,
        )
    if limit_type == LimitType.UNLIMITED and count is not None:
        raise AppException(
            code="VALIDATION_ERROR",
            message=f"{field_label} count must be empty when limit type is unlimited",
            status_code=422,
        )


def validate_plan_payload(
    *,
    role: SubscriptionPlanRole,
    teams_limit_type: LimitType,
    teams_count: int | None,
    coaches_limit_type: LimitType | None,
    coaches_count: int | None,
    players_limit_type: LimitType,
    players_count: int | None,
) -> None:
    _validate_limit_fields(
        limit_type=teams_limit_type,
        count=teams_count,
        field_label="Teams",
    )
    _validate_limit_fields(
        limit_type=players_limit_type,
        count=players_count,
        field_label="Players",
    )

    if role == SubscriptionPlanRole.ORG_ADMIN:
        if coaches_limit_type is None:
            raise AppException(
                code="VALIDATION_ERROR",
                message="Coaches limit type is required for organization plans",
                status_code=422,
            )
        _validate_limit_fields(
            limit_type=coaches_limit_type,
            count=coaches_count,
            field_label="Coaches",
        )
        return

    if coaches_limit_type is not None or coaches_count is not None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Coach plans do not support coach limit fields",
            status_code=422,
        )


async def get_plan_by_id(
    db: AsyncSession,
    plan_id: UUID,
    *,
    role: SubscriptionPlanRole | None = None,
) -> SubscriptionPlan | None:
    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id,
            SubscriptionPlan.deleted_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        return None
    if role is not None and plan.role != role.value:
        return None
    return plan


def local_plan_status(plan: SubscriptionPlan) -> PlanStatus:
    if plan.is_active and plan.archived_at is None:
        return PlanStatus.ACTIVE
    return PlanStatus.ARCHIVED


def _status_filters(status: PlanStatus):
    if status == PlanStatus.ACTIVE:
        return and_(
            SubscriptionPlan.is_active.is_(True),
            SubscriptionPlan.archived_at.is_(None),
        )
    return or_(
        SubscriptionPlan.is_active.is_(False),
        SubscriptionPlan.archived_at.is_not(None),
    )


async def sync_plans_with_stripe(
    db: AsyncSession,
    *,
    role: SubscriptionPlanRole,
) -> None:
    if not stripe_client.stripe_configured():
        return

    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.deleted_at.is_(None),
            SubscriptionPlan.role == role.value,
        )
    )
    plans = list(result.scalars().all())
    now = datetime.now(timezone.utc)
    changed = False

    for plan in plans:
        stripe_active = stripe_client.get_stripe_catalog_active(
            product_id=plan.stripe_product_id,
            price_id=plan.stripe_price_id,
        )
        local_active = plan.is_active and plan.archived_at is None

        if stripe_active is False and local_active:
            plan.is_active = False
            plan.archived_at = now
            changed = True
            continue

        if stripe_active is True and not local_active:
            try:
                stripe_client.archive_stripe_price(plan.stripe_price_id)
                stripe_client.archive_stripe_product(plan.stripe_product_id)
            except Exception:
                logger.exception(
                    "Failed to archive Stripe catalog for locally archived plan %s",
                    plan.id,
                )
            if plan.is_active:
                plan.is_active = False
                changed = True
            if plan.archived_at is None:
                plan.archived_at = now
                changed = True
            continue

        if not local_active and (plan.is_active or plan.archived_at is None):
            plan.is_active = False
            if plan.archived_at is None:
                plan.archived_at = now
            changed = True

    if changed:
        await db.commit()


async def list_plans(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    role: SubscriptionPlanRole,
    status: PlanStatus | None = None,
    billing_frequency: BillingFrequency | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> tuple[list[SubscriptionPlan], int, dict[str, int]]:
    await sync_plans_with_stripe(db, role=role)

    base_filters = [
        SubscriptionPlan.deleted_at.is_(None),
        SubscriptionPlan.role == role.value,
    ]
    if billing_frequency is not None:
        base_filters.append(SubscriptionPlan.billing_frequency == billing_frequency.value)
    if search:
        term = search.strip()
        if term:
            pattern = f"%{term}%"
            base_filters.append(
                or_(
                    SubscriptionPlan.name.ilike(pattern),
                    SubscriptionPlan.description.ilike(pattern),
                )
            )

    filters = list(base_filters)
    if status is not None:
        filters.append(_status_filters(status))
    elif is_active is not None:
        filters.append(
            _status_filters(PlanStatus.ACTIVE if is_active else PlanStatus.ARCHIVED)
        )

    total = await db.scalar(
        select(func.count()).select_from(SubscriptionPlan).where(*filters)
    ) or 0
    active_count = await db.scalar(
        select(func.count())
        .select_from(SubscriptionPlan)
        .where(*base_filters, _status_filters(PlanStatus.ACTIVE))
    ) or 0
    archived_count = await db.scalar(
        select(func.count())
        .select_from(SubscriptionPlan)
        .where(*base_filters, _status_filters(PlanStatus.ARCHIVED))
    ) or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(SubscriptionPlan)
        .where(*filters)
        .order_by(SubscriptionPlan.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(result.scalars().all())
    if status is not None:
        items = [plan for plan in items if local_plan_status(plan) == status]
    elif is_active is not None:
        expected = PlanStatus.ACTIVE if is_active else PlanStatus.ARCHIVED
        items = [plan for plan in items if local_plan_status(plan) == expected]

    return (
        items,
        total,
        {"active": active_count, "archived": archived_count},
    )


async def create_plan(
    db: AsyncSession,
    *,
    role: SubscriptionPlanRole,
    name: str,
    billing_frequency: BillingFrequency,
    currency: str,
    price_amount: Decimal,
    teams_limit_type: LimitType,
    teams_count: int | None,
    coaches_limit_type: LimitType | None,
    coaches_count: int | None,
    players_limit_type: LimitType,
    players_count: int | None,
    historical_records_duration: HistoricalRecordsDuration,
    is_active: bool,
    include_offline_sync: bool,
    description: str | None,
    features: list[str],
) -> SubscriptionPlan:
    if not stripe_client.stripe_configured():
        raise AppException(
            code="STRIPE_NOT_CONFIGURED",
            message="Stripe is not configured on the server",
            status_code=503,
        )

    validate_plan_payload(
        role=role,
        teams_limit_type=teams_limit_type,
        teams_count=teams_count,
        coaches_limit_type=coaches_limit_type,
        coaches_count=coaches_count,
        players_limit_type=players_limit_type,
        players_count=players_count,
    )

    normalized_currency = currency.strip().upper()
    if len(normalized_currency) != 3:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Currency must be a 3-letter ISO code",
            status_code=422,
        )

    amount_cents = decimal_to_cents(price_amount)
    if amount_cents < 0:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Price must be zero or greater",
            status_code=422,
        )

    metadata = {
        "role": role.value,
        "billing_frequency": billing_frequency.value,
    }
    stripe_product_id = stripe_client.create_stripe_product(
        name=name,
        description=description,
        metadata=metadata,
    )
    stripe_price_id = stripe_client.create_stripe_price(
        product_id=stripe_product_id,
        currency=normalized_currency,
        unit_amount_cents=amount_cents,
        billing_frequency=billing_frequency.value,
    )

    plan = SubscriptionPlan(
        role=role.value,
        name=name.strip(),
        billing_frequency=billing_frequency.value,
        currency=normalized_currency,
        price_amount_cents=amount_cents,
        stripe_product_id=stripe_product_id,
        stripe_price_id=stripe_price_id,
        teams_limit_type=teams_limit_type.value,
        teams_count=teams_count,
        coaches_limit_type=coaches_limit_type.value if coaches_limit_type else None,
        coaches_count=coaches_count,
        players_limit_type=players_limit_type.value,
        players_count=players_count,
        historical_records_duration=historical_records_duration.value,
        is_active=is_active,
        include_offline_sync=include_offline_sync,
        description=description.strip() if description else None,
        features=features,
    )
    db.add(plan)
    try:
        await db.commit()
        await db.refresh(plan)
    except Exception:
        await db.rollback()
        try:
            stripe_client.archive_stripe_price(stripe_price_id)
            stripe_client.archive_stripe_product(stripe_product_id)
        except Exception:
            logger.exception(
                "Failed to archive Stripe product %s after plan create rollback",
                stripe_product_id,
            )
        raise
    return plan


async def update_plan(
    db: AsyncSession,
    plan: SubscriptionPlan,
    *,
    name: str | None = None,
    price_amount: Decimal | None = None,
    teams_limit_type: LimitType | None = None,
    teams_count: int | None = None,
    coaches_limit_type: LimitType | None = None,
    coaches_count: int | None = None,
    players_limit_type: LimitType | None = None,
    players_count: int | None = None,
    historical_records_duration: HistoricalRecordsDuration | None = None,
    is_active: bool | None = None,
    include_offline_sync: bool | None = None,
    description: str | None = None,
    features: list[str] | None = None,
    currency: str | None = None,
    billing_frequency: BillingFrequency | None = None,
) -> SubscriptionPlan:
    if currency is not None and currency.strip().upper() != plan.currency:
        raise AppException(
            code="IMMUTABLE_FIELD",
            message="Currency cannot be changed after plan creation",
            status_code=400,
        )
    if billing_frequency is not None and billing_frequency.value != plan.billing_frequency:
        raise AppException(
            code="IMMUTABLE_FIELD",
            message="Billing frequency cannot be changed after plan creation",
            status_code=400,
        )

    next_role = SubscriptionPlanRole(plan.role)
    next_teams_limit_type = (
        teams_limit_type if teams_limit_type is not None else LimitType(plan.teams_limit_type)
    )
    next_teams_count = teams_count if teams_limit_type is not None else plan.teams_count
    if teams_limit_type is None and teams_count is not None:
        next_teams_count = teams_count

    next_coaches_limit_type = (
        LimitType(plan.coaches_limit_type)
        if plan.coaches_limit_type is not None
        else None
    )
    if coaches_limit_type is not None:
        next_coaches_limit_type = coaches_limit_type
    next_coaches_count = coaches_count if coaches_limit_type is not None else plan.coaches_count
    if coaches_limit_type is None and coaches_count is not None:
        next_coaches_count = coaches_count

    next_players_limit_type = (
        players_limit_type
        if players_limit_type is not None
        else LimitType(plan.players_limit_type)
    )
    next_players_count = players_count if players_limit_type is not None else plan.players_count
    if players_limit_type is None and players_count is not None:
        next_players_count = players_count

    validate_plan_payload(
        role=next_role,
        teams_limit_type=next_teams_limit_type,
        teams_count=next_teams_count,
        coaches_limit_type=next_coaches_limit_type,
        coaches_count=next_coaches_count,
        players_limit_type=next_players_limit_type,
        players_count=next_players_count,
    )

    old_price_cents = plan.price_amount_cents
    price_changed = False
    new_price_id = plan.stripe_price_id

    if price_amount is not None:
        new_price_cents = decimal_to_cents(price_amount)
        if new_price_cents < 0:
            raise AppException(
                code="VALIDATION_ERROR",
                message="Price must be zero or greater",
                status_code=422,
            )
        if new_price_cents != old_price_cents:
            if not stripe_client.stripe_configured():
                raise AppException(
                    code="STRIPE_NOT_CONFIGURED",
                    message="Stripe is not configured on the server",
                    status_code=503,
                )
            new_price_id = stripe_client.create_stripe_price(
                product_id=plan.stripe_product_id,
                currency=plan.currency,
                unit_amount_cents=new_price_cents,
                billing_frequency=plan.billing_frequency,
            )
            stripe_client.archive_stripe_price(plan.stripe_price_id)
            plan.price_amount_cents = new_price_cents
            plan.stripe_price_id = new_price_id
            price_changed = True

    if name is not None:
        plan.name = name.strip()
    plan.teams_limit_type = next_teams_limit_type.value
    plan.teams_count = next_teams_count
    plan.coaches_limit_type = (
        next_coaches_limit_type.value if next_coaches_limit_type is not None else None
    )
    plan.coaches_count = next_coaches_count
    plan.players_limit_type = next_players_limit_type.value
    plan.players_count = next_players_count
    if historical_records_duration is not None:
        plan.historical_records_duration = historical_records_duration.value
    if is_active is not None:
        plan.is_active = is_active
    if include_offline_sync is not None:
        plan.include_offline_sync = include_offline_sync
    if description is not None:
        plan.description = description.strip() or None
    if features is not None:
        plan.features = features

    await db.commit()
    await db.refresh(plan)

    if price_changed:
        await _migrate_subscribers_to_new_price(
            db,
            plan=plan,
            old_price_cents=old_price_cents,
            new_price_id=new_price_id,
        )

    return plan


async def _migrate_subscribers_to_new_price(
    db: AsyncSession,
    *,
    plan: SubscriptionPlan,
    old_price_cents: int,
    new_price_id: str,
) -> None:
    result = await db.execute(
        select(StripeSubscription).where(
            StripeSubscription.plan_id == plan.id,
            StripeSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
    )
    subscriptions = list(result.scalars().all())
    if not subscriptions:
        return

    old_price_display = format_price(old_price_cents, plan.currency)
    new_price_display = format_price(plan.price_amount_cents, plan.currency)
    billing_label = "Monthly" if plan.billing_frequency == BillingFrequency.MONTHLY.value else "Yearly"

    for subscription in subscriptions:
        try:
            stripe_client.migrate_subscription_to_new_price(
                stripe_subscription_id=subscription.stripe_subscription_id,
                new_price_id=new_price_id,
            )
            subscription.stripe_price_id = new_price_id
            try:
                send_subscription_price_change_email(
                    to_email=subscription.subscriber_email,
                    plan_name=plan.name,
                    old_price=old_price_display,
                    new_price=new_price_display,
                    billing_frequency=billing_label,
                )
            except Exception:
                logger.exception(
                    "Failed to send price-change email to %s",
                    subscription.subscriber_email,
                )
        except Exception:
            logger.exception(
                "Failed to migrate Stripe subscription %s to new price %s",
                subscription.stripe_subscription_id,
                new_price_id,
            )

    await db.commit()


async def _resolve_replacement_plan(
    db: AsyncSession,
    *,
    plan: SubscriptionPlan,
    replacement_plan_id: UUID | None,
) -> SubscriptionPlan | None:
    if replacement_plan_id is None:
        result = await db.execute(
            select(SubscriptionPlan)
            .where(
                SubscriptionPlan.id != plan.id,
                SubscriptionPlan.role == plan.role,
                SubscriptionPlan.billing_frequency == plan.billing_frequency,
                SubscriptionPlan.name.ilike(plan.name),
                SubscriptionPlan.is_active.is_(True),
                SubscriptionPlan.deleted_at.is_(None),
                SubscriptionPlan.archived_at.is_(None),
            )
            .order_by(SubscriptionPlan.created_at.desc())
        )
        return result.scalars().first()

    if replacement_plan_id == plan.id:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Replacement plan cannot be the same as the archived plan",
            status_code=422,
        )

    replacement = await get_plan_by_id(db, replacement_plan_id)
    if replacement is None or replacement.role != plan.role:
        raise AppException(
            code="PLAN_NOT_FOUND",
            message="Replacement subscription plan not found for the specified role",
            status_code=404,
        )
    if not replacement.is_active or replacement.archived_at is not None:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Replacement plan must be an active unarchived plan",
            status_code=422,
        )
    if replacement.billing_frequency != plan.billing_frequency:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Replacement plan must use the same billing frequency",
            status_code=422,
        )
    if replacement.currency != plan.currency:
        raise AppException(
            code="VALIDATION_ERROR",
            message="Replacement plan must use the same currency",
            status_code=422,
        )
    return replacement


def _format_period_end(period_end_ts: int | None) -> str | None:
    if not period_end_ts:
        return None
    return datetime.fromtimestamp(period_end_ts, tz=timezone.utc).strftime("%d %b %Y")


async def archive_plan(
    db: AsyncSession,
    plan: SubscriptionPlan,
    *,
    replacement_plan_id: UUID | None = None,
) -> SubscriptionPlan:
    if plan.archived_at is not None and not plan.is_active:
        return plan

    replacement = await _resolve_replacement_plan(
        db,
        plan=plan,
        replacement_plan_id=replacement_plan_id,
    )

    result = await db.execute(
        select(StripeSubscription).where(
            StripeSubscription.plan_id == plan.id,
            StripeSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
    )
    subscriptions = list(result.scalars().all())
    billing_label = (
        "Monthly" if plan.billing_frequency == BillingFrequency.MONTHLY.value else "Yearly"
    )
    replacement_name = replacement.name if replacement else None

    if stripe_client.stripe_configured():
        try:
            stripe_client.archive_stripe_price(plan.stripe_price_id)
            stripe_client.archive_stripe_product(plan.stripe_product_id)
        except Exception:
            logger.exception(
                "Failed to archive Stripe product/price for plan %s",
                plan.id,
            )

    for subscription in subscriptions:
        period_end_ts = None
        if stripe_client.stripe_configured():
            try:
                if replacement is not None:
                    period_end_ts = stripe_client.schedule_subscription_price_change_at_period_end(
                        stripe_subscription_id=subscription.stripe_subscription_id,
                        new_price_id=replacement.stripe_price_id,
                    )
                    subscription.pending_plan_id = replacement.id
                else:
                    period_end_ts = stripe_client.get_subscription_current_period_end(
                        subscription.stripe_subscription_id
                    )
            except Exception:
                logger.exception(
                    "Failed to schedule period-end migration for Stripe subscription %s",
                    subscription.stripe_subscription_id,
                )

        try:
            send_subscription_plan_archived_email(
                to_email=subscription.subscriber_email,
                plan_name=plan.name,
                billing_frequency=billing_label,
                period_end=_format_period_end(period_end_ts),
                replacement_plan_name=replacement_name,
            )
        except Exception:
            logger.exception(
                "Failed to send plan-archive email to %s",
                subscription.subscriber_email,
            )

    plan.is_active = False
    plan.archived_at = datetime.now(timezone.utc)
    plan.replacement_plan_id = replacement.id if replacement else None
    plan.deleted_at = None
    await db.commit()
    await db.refresh(plan)
    return plan


async def delete_plan(
    db: AsyncSession,
    plan: SubscriptionPlan,
    *,
    replacement_plan_id: UUID | None = None,
) -> SubscriptionPlan:
    return await archive_plan(db, plan, replacement_plan_id=replacement_plan_id)


def build_pagination_meta(total: int, page: int, page_size: int) -> dict[str, int | bool]:
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1 and total_pages > 0,
    }
