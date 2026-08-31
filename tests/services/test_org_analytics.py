"""Unit tests for organization admin analytics service (HE-452)."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppException
from app.schemas.org_analytics import AnalyticsFilters, AnalyticsMetrics
from app.services import org_analytics as org_analytics_service


def test_build_insights_from_metrics() -> None:
    metrics = AnalyticsMetrics(
        total_coaches=2,
        total_players=5,
        total_sessions=3,
        total_makes=10,
        total_attempts=20,
        shooting_percent=50,
    )
    insights = org_analytics_service._build_insights(metrics)
    assert any("practice sessions" in insight for insight in insights)
    assert any("50%" in insight for insight in insights)


def test_build_insights_empty_metrics() -> None:
    metrics = AnalyticsMetrics(
        total_coaches=0,
        total_players=0,
        total_sessions=0,
        total_makes=0,
        total_attempts=0,
        shooting_percent=0,
    )
    insights = org_analytics_service._build_insights(metrics)
    assert insights == ["No significant trends identified for the selected period."]


def test_raise_when_empty_raises_404() -> None:
    metrics = AnalyticsMetrics(
        total_coaches=0,
        total_players=0,
        total_sessions=0,
        total_makes=0,
        total_attempts=0,
        shooting_percent=0,
    )
    with pytest.raises(AppException) as exc_info:
        org_analytics_service._raise_when_empty(metrics)
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "ANALYTICS_NOT_FOUND"


def test_build_csv_content_includes_insights() -> None:
    from uuid import uuid4

    filters = AnalyticsFilters(date_range="2023-01-01 to 2023-12-31")
    metrics = AnalyticsMetrics(
        total_coaches=1,
        total_players=2,
        total_sessions=1,
        total_makes=5,
        total_attempts=10,
        shooting_percent=50,
    )
    export_id = uuid4()
    content = org_analytics_service._build_csv_content(metrics, filters, export_id)
    text = content.decode("utf-8")
    assert "insight_1" in text
    assert str(export_id) in text
