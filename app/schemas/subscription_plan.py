from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    BillingFrequency,
    HistoricalRecordsDuration,
    LimitType,
    PlanStatus,
    SubscriptionPlanRole,
)
from app.schemas.pagination import PaginationMeta


class CurrencyItem(BaseModel):
    code: str
    name: str


class CurrencyListResponse(BaseModel):
    items: list[CurrencyItem]


class SubscriptionPlanCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "org_admin",
                "name": "Starter Plan",
                "billing_frequency": "monthly",
                "currency": "USD",
                "price_amount": "49.00",
                "teams_limit_type": "limited",
                "teams_count": 3,
                "coaches_limit_type": "limited",
                "coaches_count": 3,
                "players_limit_type": "limited",
                "players_count": 45,
                "historical_records_duration": "3_months",
                "is_active": True,
                "include_offline_sync": False,
                "description": "Suitable for small basketball academies.",
                "features": [
                    "Online Practice Session Recording",
                    "Basic Player & Team Statistics",
                ],
            }
        }
    )

    role: SubscriptionPlanRole
    name: str = Field(min_length=1, max_length=255)
    billing_frequency: BillingFrequency
    currency: str = Field(min_length=3, max_length=3)
    price_amount: Decimal = Field(ge=0)
    teams_limit_type: LimitType
    teams_count: int | None = Field(default=None, ge=1)
    coaches_limit_type: LimitType | None = None
    coaches_count: int | None = Field(default=None, ge=1)
    players_limit_type: LimitType
    players_count: int | None = Field(default=None, ge=1)
    historical_records_duration: HistoricalRecordsDuration
    is_active: bool = True
    include_offline_sync: bool = False
    description: str | None = None
    features: list[str] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("features")
    @classmethod
    def strip_features(cls, value: list[str]) -> list[str]:
        return [feature.strip() for feature in value if feature.strip()]


class SubscriptionPlanUpdateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Starter Plan",
                "price_amount": "59.00",
                "teams_limit_type": "limited",
                "teams_count": 3,
                "coaches_limit_type": "limited",
                "coaches_count": 3,
                "players_limit_type": "limited",
                "players_count": 45,
                "historical_records_duration": "3_months",
                "is_active": True,
                "include_offline_sync": False,
                "description": "Updated description",
                "features": ["Online Practice Session Recording"],
            }
        }
    )

    name: str | None = Field(default=None, min_length=1, max_length=255)
    billing_frequency: BillingFrequency | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    price_amount: Decimal | None = Field(default=None, ge=0)
    teams_limit_type: LimitType | None = None
    teams_count: int | None = Field(default=None, ge=1)
    coaches_limit_type: LimitType | None = None
    coaches_count: int | None = Field(default=None, ge=1)
    players_limit_type: LimitType | None = None
    players_count: int | None = Field(default=None, ge=1)
    historical_records_duration: HistoricalRecordsDuration | None = None
    is_active: bool | None = None
    include_offline_sync: bool | None = None
    description: str | None = None
    features: list[str] | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()

    @field_validator("features")
    @classmethod
    def strip_features(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [feature.strip() for feature in value if feature.strip()]


class SubscriptionPlanItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: SubscriptionPlanRole
    name: str
    billing_frequency: BillingFrequency
    currency: str
    price_amount: Decimal
    stripe_product_id: str
    stripe_price_id: str
    teams_limit_type: LimitType
    teams_count: int | None
    coaches_limit_type: LimitType | None
    coaches_count: int | None
    players_limit_type: LimitType
    players_count: int | None
    historical_records_duration: HistoricalRecordsDuration
    is_active: bool
    include_offline_sync: bool
    status: PlanStatus
    archived_at: datetime | None = None
    replacement_plan_id: UUID | None = None
    stripe_status: PlanStatus | None = None
    description: str | None
    features: list[str]
    created_at: datetime
    updated_at: datetime


class SubscriptionPlanStatusCounts(BaseModel):
    active: int
    archived: int


class SubscriptionPlanListResponse(BaseModel):
    items: list[SubscriptionPlanItem]
    pagination: PaginationMeta
    counts: SubscriptionPlanStatusCounts


class SubscriptionPlanDeleteResponse(BaseModel):
    message: str
