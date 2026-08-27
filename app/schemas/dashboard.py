from typing import Any

from pydantic import BaseModel, ConfigDict, Field

DASHBOARD_EXAMPLE = {
    "total_organizations": 100,
    "total_coaches": 50,
    "total_players": 200,
    "total_sessions": 150,
    "active_subscriptions": 75,
    "revenue_overview": 5000,
    "description": None,
    "link": None,
    "error": None,
}


class DashboardAnalyticsResponse(BaseModel):
    """Super Admin dashboard KPI payload returned by GET `/super-admin/dashboard`."""

    model_config = ConfigDict(json_schema_extra={"example": DASHBOARD_EXAMPLE})

    total_organizations: int = Field(
        ge=0,
        description="Count of all organization rows",
        examples=[100],
    )
    total_coaches: int = Field(
        ge=0,
        description="Count of non-deleted user accounts with role `coach`",
        examples=[50],
    )
    total_players: int = Field(
        ge=0,
        description="Count of non-deleted user accounts with role `player`",
        examples=[200],
    )
    total_sessions: int = Field(
        ge=0,
        description="Count of `practice_sessions` rows, or 0 if that table is not present",
        examples=[150],
    )
    active_subscriptions: int = Field(
        ge=0,
        description=(
            "Count of Stripe subscriptions in live statuses "
            "(`active`, `trialing`, `past_due`)"
        ),
        examples=[75],
    )
    revenue_overview: int = Field(
        ge=0,
        description=(
            "Estimated monthly recurring list-price revenue in whole currency units "
            "(dollars), from live Stripe subscriptions joined to plan prices. "
            "Yearly plans are divided by 12."
        ),
        examples=[5000],
    )
    description: str | None = Field(
        default=None,
        description="Optional dashboard subtitle for the Super Admin UI. Always null here.",
        examples=[None],
    )
    link: str | None = Field(
        default=None,
        description=(
            "Optional related resource URL. Core-module navigation is client-side; "
            "this aggregate endpoint does not return a single resource link."
        ),
        examples=[None],
    )
    error: Any | None = Field(
        default=None,
        description=(
            "Always null on HTTP 200. Failures use the standard error envelope "
            "(`success`, `error.code`, `error.message`)."
        ),
        examples=[None],
    )
