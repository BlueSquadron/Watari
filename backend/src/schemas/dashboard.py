"""Dashboard metric schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SeverityCountPoint(BaseModel):
    severity: str
    count: int


class StatusCountPoint(BaseModel):
    status: str
    count: int


class OutcomeCountPoint(BaseModel):
    outcome: str
    count: int


class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    value: float


class AnalystWorkloadPoint(BaseModel):
    analyst_id: str
    analyst_name: str
    open_cases: int
    resolved_cases_7d: int


class DashboardMetricsResponse(BaseModel):
    open_cases_by_severity: list[SeverityCountPoint]
    cases_by_status: list[StatusCountPoint]
    cases_by_outcome: list[OutcomeCountPoint]
    mean_time_to_resolution_hours: float | None
    cases_created_over_time: list[TimeSeriesPoint]
    analyst_workload: list[AnalystWorkloadPoint]


__all__ = [
    "SeverityCountPoint",
    "StatusCountPoint",
    "OutcomeCountPoint",
    "TimeSeriesPoint",
    "AnalystWorkloadPoint",
    "DashboardMetricsResponse",
]
