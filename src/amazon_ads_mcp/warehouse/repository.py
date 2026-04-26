"""Repository helpers for warehouse dimensions, facts, metadata, and watermarks."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from sqlalchemy import Connection, Select, and_, case, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .schema import (
    ads_profile,
    freshness_watermark,
    ingestion_job,
    portfolio,
    portfolio_budget_usage_snapshot,
    report_run,
    sp_ad_group,
    sp_campaign,
    sp_campaign_budget_history_fact,
    sp_impression_share_fact,
    sp_keyword,
    sp_keyword_performance_fact,
    sp_placement_fact,
    sp_search_term_fact,
)
from .types import ACTIVE_REPORT_STATUSES, JobRecord, JobScope, ReportRunRecord
from .utils import (
    build_active_report_scope_key,
    build_job_key,
    default_worker_id,
    normalize_date,
    utcnow,
)


DIMENSION_TABLES = {
    "ads_profile": ads_profile,
    "portfolio": portfolio,
    "sp_campaign": sp_campaign,
    "sp_ad_group": sp_ad_group,
    "sp_keyword": sp_keyword,
}

FACT_TABLES = {
    "sp_keyword_performance_fact": sp_keyword_performance_fact,
    "sp_search_term_fact": sp_search_term_fact,
    "sp_campaign_budget_history_fact": sp_campaign_budget_history_fact,
    "sp_placement_fact": sp_placement_fact,
    "sp_impression_share_fact": sp_impression_share_fact,
    "portfolio_budget_usage_snapshot": portfolio_budget_usage_snapshot,
}


def _coerce_record(row: Any) -> dict[str, Any]:
    mapping = getattr(row, "_mapping", row)
    return dict(mapping)


def _insert_for_connection(connection: Connection, table):
    if connection.dialect.name == "sqlite":
        return sqlite_insert(table)
    return pg_insert(table)


def _row_to_job(row: Any) -> JobRecord:
    data = _coerce_record(row)
    data["scope"] = data.pop("scope_json") or {}
    data["diagnostic"] = data.pop("diagnostic_json") or {}
    return JobRecord(**data)


def _row_to_report_run(row: Any) -> ReportRunRecord:
    data = _coerce_record(row)
    data["diagnostic"] = data.pop("diagnostic_json") or {}
    return ReportRunRecord(**data)


def bulk_upsert(connection: Connection, table, rows: Iterable[dict[str, Any]]) -> int:
    """Upsert multiple rows into a warehouse table and return affected count."""
    materialized_rows = [dict(row) for row in rows]
    if not materialized_rows:
        return 0

    statement = _insert_for_connection(connection, table).values(materialized_rows)
    pk_columns = [column.name for column in table.primary_key.columns]
    update_columns = {
        column.name: statement.excluded[column.name]
        for column in table.columns
        if column.name not in pk_columns and column.name != "first_seen_at"
    }
    connection.execute(
        statement.on_conflict_do_update(
            index_elements=pk_columns,
            set_=update_columns,
        )
    )
    return len(materialized_rows)


def upsert_dimension_rows(
    connection: Connection,
    table_name: str,
    rows: Iterable[dict[str, Any]],
) -> int:
    """Upsert dimension rows by logical table name."""
    table = DIMENSION_TABLES[table_name]
    return bulk_upsert(connection, table, rows)


def upsert_fact_rows(
    connection: Connection,
    table_name: str,
    rows: Iterable[dict[str, Any]],
) -> int:
    """Upsert fact rows by logical table name."""
    table = FACT_TABLES[table_name]
    return bulk_upsert(connection, table, rows)


def create_or_refresh_job(connection: Connection, scope: JobScope) -> JobRecord:
    """Create or refresh a deterministic ingestion job row."""
    now = utcnow()
    job_key = build_job_key(scope)
    connection.execute(
        _insert_for_connection(connection, ads_profile)
        .values(
            profile_id=scope.profile_id,
            region=scope.region,
            first_seen_at=now,
            last_refreshed_at=now,
        )
        .on_conflict_do_update(
            index_elements=[ads_profile.c.profile_id],
            set_={
                "region": scope.region,
                "last_refreshed_at": now,
            },
        )
    )
    statement = _insert_for_connection(connection, ingestion_job).values(
        ingestion_job_id=str(uuid.uuid4()),
        job_key=job_key,
        job_type=scope.job_type,
        surface_name=scope.surface_name,
        profile_id=scope.profile_id,
        region=scope.region,
        window_start=scope.window_start,
        window_end=scope.window_end,
        scheduled_at=now,
        status="scheduled",
        scope_json=scope.scope,
        diagnostic_json={},
        attempt_count=0,
    )
    result = connection.execute(
        statement.on_conflict_do_update(
            index_elements=[ingestion_job.c.job_key],
            set_={
                "scheduled_at": now,
                "scope_json": statement.excluded.scope_json,
                "window_start": statement.excluded.window_start,
                "window_end": statement.excluded.window_end,
                "region": statement.excluded.region,
                "profile_id": statement.excluded.profile_id,
            },
        ).returning(ingestion_job)
    )
    return _row_to_job(result.one())


def claim_job(
    connection: Connection,
    scope: JobScope,
    *,
    worker_id: str | None = None,
    claim_timeout_seconds: int = 1800,
) -> JobRecord | None:
    """Claim a deterministic job for execution, reclaiming stale runs when needed."""
    job = create_or_refresh_job(connection, scope)
    now = utcnow()
    stale_before = now - timedelta(seconds=max(claim_timeout_seconds, 0))
    resolved_worker_id = worker_id or default_worker_id()
    claimable = and_(
        ingestion_job.c.job_key == job.job_key,
        case(
            (
                ingestion_job.c.status.in_(
                    ["scheduled", "failed", "cancelled", "completed"]
                ),
                True,
            ),
            (
                and_(
                    ingestion_job.c.status == "running",
                    ingestion_job.c.last_heartbeat_at.is_not(None),
                    ingestion_job.c.last_heartbeat_at < stale_before,
                ),
                True,
            ),
            else_=False,
        ),
    )
    result = connection.execute(
        update(ingestion_job)
        .where(claimable)
        .values(
            status="running",
            worker_id=resolved_worker_id,
            claimed_at=now,
            started_at=now,
            last_heartbeat_at=now,
            completed_at=None,
            attempt_count=ingestion_job.c.attempt_count + 1,
            last_error_text=None,
        )
        .returning(ingestion_job)
    )
    row = result.one_or_none()
    if row is None:
        current = connection.execute(
            select(ingestion_job).where(ingestion_job.c.job_key == job.job_key)
        ).one()
        current_job = _row_to_job(current)
        if current_job.status == "running" and current_job.worker_id == resolved_worker_id:
            return current_job
        return None
    return _row_to_job(row)


def heartbeat_job(connection: Connection, ingestion_job_id: str) -> None:
    """Update the job heartbeat for a running warehouse load."""
    connection.execute(
        update(ingestion_job)
        .where(ingestion_job.c.ingestion_job_id == ingestion_job_id)
        .values(last_heartbeat_at=utcnow())
    )


def finalize_job(
    connection: Connection,
    ingestion_job_id: str,
    *,
    status: str,
    last_error_text: str | None = None,
    diagnostic: dict[str, Any] | None = None,
) -> JobRecord:
    """Mark a warehouse job terminal and return the persisted state."""
    result = connection.execute(
        update(ingestion_job)
        .where(ingestion_job.c.ingestion_job_id == ingestion_job_id)
        .values(
            status=status,
            completed_at=utcnow(),
            last_error_text=last_error_text,
            diagnostic_json=diagnostic or {},
        )
        .returning(ingestion_job)
    )
    return _row_to_job(result.one())


def _active_report_lookup(
    *,
    profile_id: str,
    report_type_id: str,
    request_scope_hash: str,
    window_start: Any,
    window_end: Any,
) -> Select:
    return select(report_run).where(
        report_run.c.profile_id == profile_id,
        report_run.c.report_type_id == report_type_id,
        report_run.c.request_scope_hash == request_scope_hash,
        report_run.c.window_start == window_start,
        report_run.c.window_end == window_end,
    ).order_by(report_run.c.requested_at.desc())


def find_resumable_report_run(
    connection: Connection,
    *,
    profile_id: str,
    report_type_id: str,
    request_scope_hash: str,
    window_start: Any,
    window_end: Any,
) -> ReportRunRecord | None:
    """Return the newest run that can be resumed for the same report scope."""
    row = connection.execute(
        _active_report_lookup(
            profile_id=profile_id,
            report_type_id=report_type_id,
            request_scope_hash=request_scope_hash,
            window_start=window_start,
            window_end=window_end,
        )
    ).first()
    if row is None:
        return None
    candidate = _row_to_report_run(row)
    if candidate.status in ACTIVE_REPORT_STATUSES:
        return candidate
    if candidate.status == "completed" and candidate.retrieved_at is None:
        return candidate
    return None


def create_or_resume_report_run(
    connection: Connection,
    *,
    ingestion_job_id: str,
    profile_id: str,
    surface_name: str,
    report_type_id: str,
    request_scope_hash: str,
    window_start: Any,
    window_end: Any,
) -> ReportRunRecord:
    """Create a durable report run or return an already resumable one."""
    normalized_window_start = normalize_date(window_start)
    normalized_window_end = normalize_date(window_end)
    existing = find_resumable_report_run(
        connection,
        profile_id=profile_id,
        report_type_id=report_type_id,
        request_scope_hash=request_scope_hash,
        window_start=normalized_window_start,
        window_end=normalized_window_end,
    )
    if existing is not None:
        return existing

    active_scope_key = build_active_report_scope_key(
        profile_id=profile_id,
        report_type_id=report_type_id,
        request_scope_hash=request_scope_hash,
        window_start=normalized_window_start,
        window_end=normalized_window_end,
    )
    statement = _insert_for_connection(connection, report_run).values(
        report_run_id=str(uuid.uuid4()),
        ingestion_job_id=ingestion_job_id,
        profile_id=profile_id,
        window_start=normalized_window_start,
        window_end=normalized_window_end,
        surface_name=surface_name,
        report_type_id=report_type_id,
        request_scope_hash=request_scope_hash,
        active_scope_key=active_scope_key,
        status="queued",
        requested_at=utcnow(),
        diagnostic_json={},
    )
    result = connection.execute(
        statement.on_conflict_do_nothing(
            index_elements=[report_run.c.active_scope_key]
        ).returning(report_run)
    )
    row = result.one_or_none()
    if row is not None:
        return _row_to_report_run(row)
    resumed = find_resumable_report_run(
        connection,
        profile_id=profile_id,
        report_type_id=report_type_id,
        request_scope_hash=request_scope_hash,
        window_start=normalized_window_start,
        window_end=normalized_window_end,
    )
    if resumed is None:
        raise RuntimeError("Failed to create or resume report_run state.")
    return resumed


def update_report_run(
    connection: Connection,
    report_run_id: str,
    *,
    amazon_report_id: str | None = None,
    status: str | None = None,
    raw_status: str | None = None,
    status_details: str | None = None,
    diagnostic: dict[str, Any] | None = None,
    error_text: str | None = None,
    row_count: int | None = None,
    mark_polled: bool = False,
    mark_completed: bool = False,
    mark_retrieved: bool = False,
    release_active_scope: bool = False,
) -> ReportRunRecord:
    """Persist incremental report-run lifecycle updates."""
    values: dict[str, Any] = {}
    if amazon_report_id is not None:
        values["amazon_report_id"] = amazon_report_id
    if status is not None:
        values["status"] = status
    if raw_status is not None:
        values["raw_status"] = raw_status
    if status_details is not None:
        values["status_details"] = status_details
    if diagnostic is not None:
        values["diagnostic_json"] = diagnostic
    if error_text is not None:
        values["error_text"] = error_text
    if row_count is not None:
        values["row_count"] = row_count
    if mark_polled:
        values["last_polled_at"] = utcnow()
    if mark_completed:
        values["completed_at"] = utcnow()
    if mark_retrieved:
        values["retrieved_at"] = utcnow()
    if release_active_scope:
        values["active_scope_key"] = None
    result = connection.execute(
        update(report_run)
        .where(report_run.c.report_run_id == report_run_id)
        .values(**values)
        .returning(report_run)
    )
    return _row_to_report_run(result.one())


def advance_watermark(
    connection: Connection,
    *,
    surface_name: str,
    profile_id: str,
    region: str,
    last_successful_window_end: Any = None,
    last_snapshot_at: Any = None,
    last_attempted_at: Any = None,
    last_status: str | None = None,
    notes: dict[str, Any] | None = None,
) -> None:
    """Insert or update a freshness watermark for a surface/profile/region."""
    statement = _insert_for_connection(connection, freshness_watermark).values(
        surface_name=surface_name,
        profile_id=profile_id,
        region=region,
        last_successful_window_end=normalize_date(last_successful_window_end),
        last_snapshot_at=last_snapshot_at,
        last_attempted_at=last_attempted_at or utcnow(),
        last_status=last_status,
        notes_json=notes or {},
    )
    connection.execute(
        statement.on_conflict_do_update(
            index_elements=[
                freshness_watermark.c.surface_name,
                freshness_watermark.c.profile_id,
                freshness_watermark.c.region,
            ],
            set_={
                "last_successful_window_end": statement.excluded.last_successful_window_end,
                "last_snapshot_at": statement.excluded.last_snapshot_at,
                "last_attempted_at": statement.excluded.last_attempted_at,
                "last_status": statement.excluded.last_status,
                "notes_json": statement.excluded.notes_json,
            },
        )
    )
