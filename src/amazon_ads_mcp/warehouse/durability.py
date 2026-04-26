"""Durable job and report orchestration helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection

from .repository import (
    claim_job,
    create_or_resume_report_run,
    finalize_job,
    heartbeat_job,
    update_report_run,
)
from .types import JobRecord, JobScope, ReportRunRecord
from .utils import build_report_scope_hash, normalize_date


class WarehouseJobCoordinator:
    """Coordinate deterministic warehouse job claims and heartbeats."""

    def __init__(self, connection: Connection, *, claim_timeout_seconds: int) -> None:
        self.connection = connection
        self.claim_timeout_seconds = claim_timeout_seconds

    def claim(self, scope: JobScope, *, worker_id: str) -> JobRecord | None:
        """Claim the requested job scope if it is runnable."""
        return claim_job(
            self.connection,
            scope,
            worker_id=worker_id,
            claim_timeout_seconds=self.claim_timeout_seconds,
        )

    def heartbeat(self, ingestion_job_id: str) -> None:
        """Record a heartbeat for an in-flight job."""
        heartbeat_job(self.connection, ingestion_job_id)

    def complete(self, ingestion_job_id: str, *, diagnostic: dict[str, Any] | None = None) -> JobRecord:
        """Finalize a job successfully."""
        return finalize_job(
            self.connection,
            ingestion_job_id,
            status="completed",
            diagnostic=diagnostic,
        )

    def fail(
        self,
        ingestion_job_id: str,
        *,
        error_text: str,
        diagnostic: dict[str, Any] | None = None,
    ) -> JobRecord:
        """Finalize a job as failed."""
        return finalize_job(
            self.connection,
            ingestion_job_id,
            status="failed",
            last_error_text=error_text,
            diagnostic=diagnostic,
        )


class DurableReportCoordinator:
    """Persist report-run lifecycle state for restart-safe report ingestion."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def create_or_resume(
        self,
        *,
        ingestion_job_id: str,
        profile_id: str,
        region: str,
        request,
    ) -> ReportRunRecord:
        """Return an existing resumable report run or create a new one."""
        request_scope_hash = build_report_scope_hash(
            profile_id=profile_id,
            region=region,
            request=request,
        )
        return create_or_resume_report_run(
            self.connection,
            ingestion_job_id=ingestion_job_id,
            profile_id=profile_id,
            surface_name=request.surface_name,
            report_type_id=request.report_type_id,
            request_scope_hash=request_scope_hash,
            window_start=normalize_date(request.start_date),
            window_end=normalize_date(request.end_date),
        )

    def store_amazon_report_id(self, report_run_id: str, amazon_report_id: str) -> ReportRunRecord:
        """Attach the created Amazon report id to a durable run."""
        return update_report_run(
            self.connection,
            report_run_id,
            amazon_report_id=amazon_report_id,
            status="queued",
        )

    def mark_polled(
        self,
        report_run_id: str,
        *,
        status: str,
        raw_status: str | None,
        status_details: str | None,
        diagnostic: dict[str, Any] | None = None,
    ) -> ReportRunRecord:
        """Persist a polled lifecycle update."""
        normalized_status = status.lower()
        release_active_scope = normalized_status in {"failed", "cancelled"}
        return update_report_run(
            self.connection,
            report_run_id,
            status=normalized_status,
            raw_status=raw_status,
            status_details=status_details,
            diagnostic=diagnostic,
            mark_polled=True,
            mark_completed=status == "COMPLETED",
            release_active_scope=release_active_scope,
        )

    def mark_downloaded(
        self,
        report_run_id: str,
        *,
        row_count: int,
        diagnostic: dict[str, Any] | None = None,
    ) -> ReportRunRecord:
        """Persist successful report retrieval state."""
        return update_report_run(
            self.connection,
            report_run_id,
            status="completed",
            row_count=row_count,
            diagnostic=diagnostic,
            mark_retrieved=True,
            release_active_scope=True,
        )

    def mark_failed(
        self,
        report_run_id: str,
        *,
        error_text: str,
        raw_status: str | None = None,
        status_details: str | None = None,
        diagnostic: dict[str, Any] | None = None,
    ) -> ReportRunRecord:
        """Persist terminal failure state for a report run."""
        return update_report_run(
            self.connection,
            report_run_id,
            status="failed",
            raw_status=raw_status,
            status_details=status_details,
            diagnostic=diagnostic,
            error_text=error_text,
            mark_completed=True,
            release_active_scope=True,
        )
