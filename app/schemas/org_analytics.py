"""Pydantic schemas for organization admin analytics API (HE-452)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.org_reports import ReportCriteria, ReportMetrics

ANALYTICS_FILTERS_EXAMPLE = {
    "date_range": "2023-01-01 to 2023-12-31",
    "user_segments": ["segment1", "segment2"],
}

ANALYTICS_FILTER_REQUEST_EXAMPLE = {
    "filters": ANALYTICS_FILTERS_EXAMPLE,
}

ANALYTICS_METRICS_EXAMPLE = {
    "total_coaches": 5,
    "total_players": 20,
    "total_sessions": 12,
    "total_makes": 150,
    "total_attempts": 300,
    "shooting_percent": 50,
}

ANALYTICS_DASHBOARD_EXAMPLE = {
    "success": True,
    "message": "Analytics dashboard loaded successfully.",
    "data": ANALYTICS_METRICS_EXAMPLE,
    "filters": ANALYTICS_FILTERS_EXAMPLE,
    "insights": [
        "Organization recorded 12 practice sessions in the selected period.",
        "Shooting performance is 50%.",
    ],
    "error": None,
}


class AnalyticsFilters(ReportCriteria):
    """Filter parameters for analytics queries."""

    model_config = ConfigDict(json_schema_extra={"example": ANALYTICS_FILTERS_EXAMPLE})


class AnalyticsFilterRequest(BaseModel):
    """Payload for POST /analytics/filter."""

    model_config = ConfigDict(json_schema_extra={"example": ANALYTICS_FILTER_REQUEST_EXAMPLE})

    filters: AnalyticsFilters = Field(description="Analytics filter criteria")


class AnalyticsMetrics(ReportMetrics):
    """Org-scoped analytics metrics returned on dashboard and filter responses."""

    model_config = ConfigDict(json_schema_extra={"example": ANALYTICS_METRICS_EXAMPLE})


class AnalyticsDashboardResponse(BaseModel):
    """Analytics dashboard or filtered analytics response."""

    model_config = ConfigDict(json_schema_extra={"example": ANALYTICS_DASHBOARD_EXAMPLE})

    success: bool = Field(default=True, description="Always true on success")
    message: str = Field(description="Human-readable outcome message")
    data: AnalyticsMetrics = Field(description="Analytics metrics for the dashboard")
    filters: AnalyticsFilters = Field(description="Filters applied to compute the metrics")
    insights: list[str] = Field(
        description="Trend and insight summaries derived from the metrics",
        examples=[["Organization recorded 12 practice sessions in the selected period."]],
    )
    error: None = Field(default=None, description="Always null on success")


class AnalyticsExportRequest(BaseModel):
    """Payload for POST /analytics/export."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "filters": ANALYTICS_FILTERS_EXAMPLE,
                "format": "csv",
            }
        }
    )

    filters: AnalyticsFilters = Field(description="Filters used to compute export insights")
    format: Literal["csv", "pdf"] = Field(description="Export format: csv or pdf")

    @field_validator("format", mode="before")
    @classmethod
    def normalize_format(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class AnalyticsExportResponse(BaseModel):
    """Successful analytics export response."""

    success: bool = Field(default=True)
    message: str = Field(description="Export success message")
    format: Literal["csv", "pdf"] = Field(description="Exported format")
    content_base64: str = Field(description="Base64-encoded export file contents")
    filename: str = Field(description="Suggested download filename")
    error: None = Field(default=None)
