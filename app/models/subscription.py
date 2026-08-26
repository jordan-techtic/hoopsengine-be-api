import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.tables import (
    STRIPE_SUBSCRIPTIONS_TABLE,
    SUBSCRIPTION_PLANS_TABLE,
    USERS_TABLE,
)


class StripeSubscription(Base):
    """Managed Stripe subscription records in `stripe_subscriptions_staging`."""

    __tablename__ = STRIPE_SUBSCRIPTIONS_TABLE

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SUBSCRIPTION_PLANS_TABLE}.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subscriber_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{USERS_TABLE}.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subscriber_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stripe_subscription_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stripe_price_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    pending_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SUBSCRIPTION_PLANS_TABLE}.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
