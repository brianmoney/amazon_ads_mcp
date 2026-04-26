"""Shared types for warehouse orchestration and ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_REPORT_STATUSES = {"queued", "processing", "unknown"}
TERMINAL_REPORT_STATUSES = {"completed", "failed", "cancelled"}


@dataclass(frozen=True)
class JobScope:
    """Natural key inputs used to schedule and claim a warehouse load."""

    profile_id: str
    region: str
    surface_name: str
    job_type: str
    window_start: date | None = None
    window_end: date | None = None
    scope: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportRequest:
    """Normalized request descriptor for a report-based warehouse load."""

    surface_name: str
    report_type_id: str
    start_date: str
    end_date: str
    group_by: list[str]
    columns: list[str]
    filters: list[dict[str, Any]]
    time_unit: str = "SUMMARY"


@dataclass
class JobRecord:
    """Materialized ingestion-job state returned by the repository."""

    ingestion_job_id: str
    job_key: str
    status: str
    profile_id: str
    region: str
    surface_name: str
    job_type: str
    worker_id: str | None
    scheduled_at: datetime
    attempt_count: int
    window_start: date | None
    window_end: date | None
    scope: dict[str, Any]
    diagnostic: dict[str, Any]
    last_error_text: str | None = None
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class ReportRunRecord:
    """Materialized durable report-run state."""

    report_run_id: str
    ingestion_job_id: str
    profile_id: str
    surface_name: str
    report_type_id: str
    request_scope_hash: str
    status: str
    active_scope_key: str | None
    requested_at: datetime
    amazon_report_id: str | None = None
    raw_status: str | None = None
    status_details: str | None = None
    last_polled_at: datetime | None = None
    completed_at: datetime | None = None
    retrieved_at: datetime | None = None
    row_count: int | None = None
    error_text: str | None = None
    diagnostic: dict[str, Any] = field(default_factory=dict)
    window_start: date | None = None
    window_end: date | None = None
