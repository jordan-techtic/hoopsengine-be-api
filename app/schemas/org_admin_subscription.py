"""Pydantic schemas for organization admin subscription management APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.mobile_envelope import MobileWriteOnlyPasswordMixin

ORG_ADMIN_SUBSCRIPTION_RESPONSE_EXAMPLE = {
    "success": True,
    "message": "Subscription details loaded successfully",
    "status": "active",
    "description": "Your current subscription is active",
    "link": None,
    "error": None,
    "id": "11111111-2222-3333-4444-555555555555",
    "title": "Subscription Management",
    "name": "Pro Plan",
    "subscription_plan": "Pro Plan",
    "features_included": [
        "Unlimited Drill Library Access",
        "Team Management (up to 5 teams)",
        "Advanced Performance Analytics",
        "Priority Coach Support",
    ],
    "renewal_date": "2026-02-15",
    "billing_cycle": "monthly",
    "full_name": "Jane Doe",
    "warning": None,
    "notification": "Subscription details loaded successfully",
}


class OrgAdminSubscriptionUpgradeRequest(BaseModel):
    """Payload for POST /admin/subscription/upgrade."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "full_name": "Pro Plan",
            }
        },
    )

    plan_id: UUID | None = Field(
        default=None,
        description="UUID of the organization subscription plan to upgrade to",
        examples=["11111111-2222-3333-4444-555555555555"],
    )
    full_name: str | None = Field(
        default=None,
        description=(
            "Target plan display name from the plan-name-group field (e.g. 'Pro Plan')"
        ),
        examples=["Pro Plan"],
    )


class OrgAdminSubscriptionResponse(MobileWriteOnlyPasswordMixin):
    """Organization subscription details for the Subscription Management screen."""

    model_config = ConfigDict(
        json_schema_extra={"example": ORG_ADMIN_SUBSCRIPTION_RESPONSE_EXAMPLE}
    )

    success: bool = Field(default=True)
    message: str
    status: str = Field(description="Subscription lifecycle status for the mobile client")
    description: str | None = None
    link: str | None = None
    error: None = None
    id: UUID = Field(description="Local subscription record UUID")
    title: str = Field(default="Subscription Management")
    name: str = Field(description="Current plan display name", examples=["Pro Plan"])
    subscription_plan: str = Field(description="Current subscription plan name")
    features_included: list[str] = Field(default_factory=list)
    renewal_date: str = Field(
        description="Next renewal date in YYYY-MM-DD format",
        examples=["2026-02-15"],
    )
    billing_cycle: str = Field(description="Billing cadence for the plan", examples=["monthly"])
    full_name: str = Field(description="Organization admin display name")
    warning: str | None = Field(
        default=None,
        description="Optional warning when renewal is within five days",
    )
    notification: str | None = Field(
        default=None,
        description="UI toast/notification text for the latest action or load state",
    )
