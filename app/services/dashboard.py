from __future__ import annotations

import logging

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.enums import BillingFrequency, UserRole
from app.models.organization import Organization
from app.models.subscription import StripeSubscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.schemas.dashboard import DashboardAnalyticsResponse
from app.services.subscription_plan import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    cents_to_decimal,
)

logger = logging.getLogger(__name__)

SESSIONS_TABLE = "practice_sessions"
# Identifier is a string literal, never interpolated into SQL from a variable.
_PRACTICE_SESSIONS_COUNT_SQL = "SELECT COUNT(*) FROM practice_sessions"


def monthly_list_price_cents(price_amount_cents: int, billing_frequency: str) -> int:
    """Normalize a plan list price to monthly cents.

    Yearly prices are divided by 12 using integer division. Other frequencies
    (including monthly) are treated as already monthly.
    """
    if billing_frequency == BillingFrequency.YEARLY.value:
        return price_amount_cents // 12
    return price_amount_cents


def list_price_dollars(amount_cents: int) -> int:
    """Convert a cent amount to whole currency units matching the ticket integer field."""
    return int(cents_to_decimal(amount_cents))


async def _count_orm(db: AsyncSession, stmt: Select[tuple[int]]) -> int:
    """Execute a COUNT select and return an int, treating NULL as 0."""
    return int(await db.scalar(stmt) or 0)


async def _table_exists(db: AsyncSession, table_name: str) -> bool:
    """Return True if `public.{table_name}` exists. `table_name` is bound, not interpolated."""
    exists = await db.scalar(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :table_name
            )
            """
        ),
        {"table_name": table_name},
    )
    return bool(exists)


async def _count_practice_sessions(db: AsyncSession) -> int:
    """Return COUNT(*) of practice_sessions, or 0 if that client table is absent."""
    if not await _table_exists(db, SESSIONS_TABLE):
        return 0
    return int(await db.scalar(text(_PRACTICE_SESSIONS_COUNT_SQL)) or 0)


async def get_dashboard_analytics(db: AsyncSession) -> DashboardAnalyticsResponse:
    """Aggregate Super Admin dashboard KPIs. All-zero counts are a valid empty state."""
    total_organizations = await _count_orm(
        db, select(func.count()).select_from(Organization)
    )
    total_coaches = await _count_orm(
        db,
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.COACH.value, User.deleted_at.is_(None)),
    )
    total_players = await _count_orm(
        db,
        select(func.count())
        .select_from(User)
        .where(User.role == UserRole.PLAYER.value, User.deleted_at.is_(None)),
    )
    total_sessions = await _count_practice_sessions(db)
    active_subscriptions = await _count_orm(
        db,
        select(func.count())
        .select_from(StripeSubscription)
        .where(StripeSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES)),
    )

    result = await db.execute(
        select(
            SubscriptionPlan.price_amount_cents,
            SubscriptionPlan.billing_frequency,
        )
        .join(StripeSubscription, StripeSubscription.plan_id == SubscriptionPlan.id)
        .where(StripeSubscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES))
    )
    monthly_cents = 0
    for price_cents, frequency in result.all():
        monthly_cents += monthly_list_price_cents(int(price_cents), str(frequency))

    return DashboardAnalyticsResponse(
        total_organizations=total_organizations,
        total_coaches=total_coaches,
        total_players=total_players,
        total_sessions=total_sessions,
        active_subscriptions=active_subscriptions,
        revenue_overview=list_price_dollars(monthly_cents),
    )
