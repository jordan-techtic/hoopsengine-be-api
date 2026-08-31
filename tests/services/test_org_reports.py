"""Unit tests for organization admin report service (HE-449)."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.exceptions import AppException
from app.schemas.org_reports import ReportCriteria
from app.services import org_reports as org_reports_service


def test_parse_report_criteria_from_date_range() -> None:
    criteria = ReportCriteria(date_range="2023-01-01 to 2023-12-31", user_segments=["coach"])
    parsed = org_reports_service.parse_report_criteria(criteria)
    assert parsed.date_start == date(2023, 1, 1)
    assert parsed.date_end == date(2023, 12, 31)
    assert parsed.user_segments == ["coach"]


def test_parse_report_criteria_invalid_date_range_400() -> None:
    criteria = ReportCriteria(date_range="invalid-range")
    with pytest.raises(AppException) as exc_info:
        org_reports_service.parse_report_criteria(criteria)
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_parse_report_criteria_missing_range_400() -> None:
    criteria = ReportCriteria(user_segments=["segment1"])
    with pytest.raises(AppException) as exc_info:
        org_reports_service.parse_report_criteria(criteria)
    assert exc_info.value.status_code == 400


def test_parse_report_criteria_end_before_start_400() -> None:
    criteria = ReportCriteria(date_range="2023-12-31 to 2023-01-01")
    with pytest.raises(AppException) as exc_info:
        org_reports_service.parse_report_criteria(criteria)
    assert exc_info.value.status_code == 400


def test_metrics_are_empty_when_all_zero() -> None:
    from app.schemas.org_reports import ReportMetrics

    metrics = ReportMetrics(
        total_coaches=0,
        total_players=0,
        total_sessions=0,
        total_makes=0,
        total_attempts=0,
        shooting_percent=0,
    )
    assert org_reports_service._metrics_are_empty(metrics) is True


def test_build_csv_content_contains_metrics() -> None:
    from uuid import uuid4

    from app.models.org_report import OrgReport
    from app.schemas.org_reports import ReportMetrics

    report_id = uuid4()
    report = OrgReport(
        id=report_id,
        org_id=uuid4(),
        created_by_user_id=uuid4(),
        criteria={"date_range": "2023-01-01 to 2023-12-31"},
        metrics={},
        status="completed",
    )
    metrics = ReportMetrics(
        total_coaches=2,
        total_players=5,
        total_sessions=3,
        total_makes=10,
        total_attempts=20,
        shooting_percent=50,
    )
    content = org_reports_service._build_csv_content(report, metrics)
    text = content.decode("utf-8")
    assert "total_coaches,2" in text
    assert str(report_id) in text
