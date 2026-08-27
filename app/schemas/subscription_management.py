"""Pydantic schemas for coach subscription management APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin


class SubscriptionUpgradeRequest(BaseModel):
    """Payload for POST /subscription/upgrade."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan_id": "11111111-2222-3333-4444-555555555555",
                "full_name": "Jane Doe",
            }
        }
    )

    plan_id: UUID = Field(
        description="UUID of the subscription plan to upgrade to",
        examples=["11111111-2222-3333-4444-555555555555"],
    )
    full_name: str | None = Field(
        default=None,
        description="Optional client metadata from the plan-name-group field (not persisted)",
        examples=["Jane Doe"],
    )


class SubscriptionCancelRequest(BaseModel):
    """Payload for POST /subscription/cancel."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Jane Doe",
            }
        }
    )

    full_name: str | None = Field(
        default=None,
        description="Optional client metadata from the plan-name-group field (not persisted)",
        examples=["Jane Doe"],
    )


class SubscriptionDetailsResponse(MobileWriteOnlyPasswordMixin):
    """Current subscription details for the subscription-management screen."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Subscription details loaded successfully",
                "status": "active",
                "description": "Your current subscription is active",
                "link": None,
                "error": None,
                "id": "11111111-2222-3333-4444-555555555555",
                "title": "Subscription",
                "name": "Pro Plan",
                "current_plan": "Pro Plan",
                "expiry_date": "Feb 15, 2026",
                "features": [
                    "Unlimited Drill Library Access",
                    "Team Management (up to 5 teams)",
                    "Advanced Performance Analytics",
                    "Priority Coach Support",
                ],
                "full_name": "Jane Doe",
            }
        }
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(description="Subscription lifecycle status for the mobile client")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Local subscription record UUID")
    title: str = Field(default="Subscription", description="Screen title for the mobile client")
    name: str = Field(description="Current plan display name", examples=["Pro Plan"])
    current_plan: str = Field(description="Current plan name", examples=["Pro Plan"])
    expiry_date: str = Field(description="Formatted renewal/expiry date", examples=["Feb 15, 2026"])
    features: list[str] = Field(default_factory=list)
    full_name: str = Field(description="Subscriber full name", examples=["Jane Doe"])
