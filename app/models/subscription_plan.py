import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.tables import SUBSCRIPTION_PLANS_TABLE
from app.models.enums import (
    BillingFrequency,
    HistoricalRecordsDuration,
    LimitType,
    SubscriptionPlanRole,
)

ROLE_VALUES = ", ".join(f"'{value.value}'" for value in SubscriptionPlanRole)
BILLING_FREQUENCY_VALUES = ", ".join(f"'{value.value}'" for value in BillingFrequency)
LIMIT_TYPE_VALUES = ", ".join(f"'{value.value}'" for value in LimitType)
HISTORICAL_RECORDS_VALUES = ", ".join(
    f"'{value.value}'" for value in HistoricalRecordsDuration
)


class SubscriptionPlan(Base):
    __tablename__ = SUBSCRIPTION_PLANS_TABLE
    __table_args__ = (
        CheckConstraint(
            f"role IN ({ROLE_VALUES})",
            name=f"{SUBSCRIPTION_PLANS_TABLE}_role_check",
        ),
        CheckConstraint(
            f"billing_frequency IN ({BILLING_FREQUENCY_VALUES})",
            name=f"{SUBSCRIPTION_PLANS_TABLE}_billing_frequency_check",
        ),
        CheckConstraint(
            f"teams_limit_type IN ({LIMIT_TYPE_VALUES})",
            name=f"{SUBSCRIPTION_PLANS_TABLE}_teams_limit_type_check",
        ),
        CheckConstraint(
            f"players_limit_type IN ({LIMIT_TYPE_VALUES})",
            name=f"{SUBSCRIPTION_PLANS_TABLE}_players_limit_type_check",
        ),
        CheckConstraint(
            f"historical_records_duration IN ({HISTORICAL_RECORDS_VALUES})",
            name=f"{SUBSCRIPTION_PLANS_TABLE}_historical_records_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    billing_frequency: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    price_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    stripe_product_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    stripe_price_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    teams_limit_type: Mapped[str] = mapped_column(String(16), nullable=False)
    teams_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coaches_limit_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    coaches_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    players_limit_type: Mapped[str] = mapped_column(String(16), nullable=False)
    players_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    historical_records_duration: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_offline_sync: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    features: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    replacement_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SUBSCRIPTION_PLANS_TABLE}.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
