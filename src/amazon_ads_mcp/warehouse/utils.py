"""Small warehouse utility helpers."""

from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ..config.settings import Settings
from .types import JobScope, ReportRequest


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def normalize_date(value: str | date | None) -> date | None:
    """Normalize supported date inputs to ``date`` instances."""
    if value is None or isinstance(value, date):
        return value
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").date()
    return date.fromisoformat(text)


def normalize_datetime(value: Any) -> datetime | None:
    """Normalize common Amazon timestamp strings to timezone-aware datetimes."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def stable_json_hash(payload: dict[str, Any]) -> str:
    """Hash a JSON payload using a deterministic key order."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_job_key(scope: JobScope) -> str:
    """Create the deterministic job key required by the OpenSpec change."""
    base = {
        "profile_id": scope.profile_id,
        "region": scope.region,
        "surface_name": scope.surface_name,
        "job_type": scope.job_type,
        "window_start": scope.window_start.isoformat() if scope.window_start else None,
        "window_end": scope.window_end.isoformat() if scope.window_end else None,
        "scope": scope.scope,
    }
    return stable_json_hash(base)


def build_report_scope_hash(
    *,
    profile_id: str,
    region: str,
    request: ReportRequest,
) -> str:
    """Fingerprint a report request for restart-safe resume semantics."""
    return stable_json_hash(
        {
            "profile_id": profile_id,
            "region": region,
            "surface_name": request.surface_name,
            "report_type_id": request.report_type_id,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "group_by": request.group_by,
            "columns": request.columns,
            "filters": request.filters,
            "time_unit": request.time_unit,
        }
    )


def build_active_report_scope_key(
    *,
    profile_id: str,
    report_type_id: str,
    request_scope_hash: str,
    window_start: date | None,
    window_end: date | None,
) -> str:
    """Return the unique active-scope key for in-flight report runs."""
    return "|".join(
        [
            profile_id,
            report_type_id,
            request_scope_hash,
            window_start.isoformat() if window_start else "",
            window_end.isoformat() if window_end else "",
        ]
    )


def default_worker_id(settings: Settings | None = None) -> str:
    """Build a stable local worker identifier when none is configured."""
    resolved_settings = settings or Settings()
    if resolved_settings.warehouse_worker_id:
        return resolved_settings.warehouse_worker_id
    return f"warehouse-{socket.gethostname()}"


def report_window(settings: Settings | None = None, *, now: date | None = None) -> tuple[date, date]:
    """Return the default inclusive report window for a worker cycle."""
    resolved_settings = settings or Settings()
    window_end = now or utcnow().date()
    window_start = window_end - timedelta(
        days=max(resolved_settings.warehouse_report_window_days - 1, 0)
    )
    return window_start, window_end
