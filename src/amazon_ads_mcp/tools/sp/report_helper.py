"""Internal async report orchestration for Sponsored Products tools."""

from __future__ import annotations

import asyncio
import gzip
import json
import random
import re
import time
import uuid
from typing import Any

import httpx

from .common import get_sp_client


SP_CREATE_REPORT_MEDIA_TYPE = "application/vnd.createasyncreportrequest.v3+json"
REPORT_ID_PATTERN = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)
MIN_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
MAX_POLL_INTERVAL_SECONDS = 8.0
DEFAULT_POLL_JITTER_SECONDS = 0.25
POLL_BACKOFF_FACTOR = 1.5


class SPReportError(RuntimeError):
    """Raised when the Sponsored Products report lifecycle fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


def _build_http_error(message: str, exc: httpx.HTTPError) -> SPReportError:
    response = exc.response
    return SPReportError(
        message,
        status_code=response.status_code if response is not None else None,
        response_text=(response.text if response is not None else None),
    )


def _parse_report_rows(content: bytes) -> list[dict[str, Any]]:
    try:
        raw_payload = gzip.decompress(content)
    except OSError as exc:
        raise SPReportError(
            "Sponsored Products report payload could not be decompressed."
        ) from exc

    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SPReportError(
            "Sponsored Products report payload was not valid JSON."
        ) from exc

    if isinstance(payload, dict):
        payload = payload.get("rows", payload.get("data"))

    if not isinstance(payload, list) or not all(
        isinstance(row, dict) for row in payload
    ):
        raise SPReportError(
            "Sponsored Products report payload did not contain a row list."
        )

    return payload


def _build_report_request(
    report_type_id: str,
    start_date: str,
    end_date: str,
    group_by: list[str],
    columns: list[str],
    filters: list[dict[str, Any]] | None,
    time_unit: str,
) -> dict[str, Any]:
    return {
        "name": f"{report_type_id}-{start_date}-{end_date}-{uuid.uuid4().hex[:8]}",
        "startDate": start_date,
        "endDate": end_date,
        "configuration": {
            "adProduct": "SPONSORED_PRODUCTS",
            "reportTypeId": report_type_id,
            "groupBy": group_by,
            "columns": columns,
            "format": "GZIP_JSON",
            "timeUnit": time_unit,
            "filters": filters or [],
        },
    }


def normalize_sp_report_status(raw_status: Any) -> str:
    """Map Amazon report lifecycle states to a stable internal set."""
    normalized = str(raw_status or "").strip().upper()
    if normalized in {"SUCCESS", "COMPLETED"}:
        return "COMPLETED"
    if normalized in {"FAILURE", "FAILED", "ERROR"}:
        return "FAILED"
    if normalized in {"CANCELLED", "CANCELED"}:
        return "CANCELLED"
    if normalized in {"IN_PROGRESS", "PROCESSING", "RUNNING"}:
        return "PROCESSING"
    if normalized in {"PENDING", "QUEUED", "CREATED"}:
        return "QUEUED"
    return "UNKNOWN"


def _normalize_status_payload(
    report_id: str, status_payload: dict[str, Any]
) -> dict[str, Any]:
    raw_status = str(status_payload.get("status") or "").strip().upper()
    return {
        "report_id": str(report_id),
        "status": normalize_sp_report_status(raw_status),
        "raw_status": raw_status or None,
        "status_details": status_payload.get("statusDetails")
        or status_payload.get("failureReason")
        or status_payload.get("message"),
        "download_url": status_payload.get("url") or status_payload.get("location"),
        "generated_at": status_payload.get("generatedAt")
        or status_payload.get("generatedDate"),
        "updated_at": status_payload.get("updatedAt")
        or status_payload.get("updatedDate"),
        "url_expires_at": status_payload.get("urlExpiresAt")
        or status_payload.get("locationExpiresAt"),
    }


def _format_poll_duration(seconds: float) -> str:
    return f"{max(seconds, 0.0):.1f}s"


def _format_timeout_message(report_id: str, status: dict[str, Any], elapsed: float) -> str:
    return (
        f"Sponsored Products report {report_id} timed out while polling after "
        f"{_format_poll_duration(elapsed)} (last status: {status['status']})."
    )


def _format_terminal_status_message(
    report_id: str, status: dict[str, Any], elapsed: float
) -> str:
    message = (
        f"Sponsored Products report {report_id} failed with status "
        f"{status['status']} after {_format_poll_duration(elapsed)}"
    )
    if status.get("status_details"):
        message = f"{message}: {status['status_details']}"
    else:
        message = f"{message}."
    return message


def _format_not_ready_message(report_id: str, status: dict[str, Any]) -> str:
    message = (
        f"Sponsored Products report {report_id} is not ready "
        f"(status: {status['status']})."
    )
    if status.get("status_details"):
        return f"{message[:-1]} {status['status_details']}."
    return message


async def create_sp_report(
    *,
    report_type_id: str,
    start_date: str,
    end_date: str,
    group_by: list[str],
    columns: list[str],
    filters: list[dict[str, Any]] | None = None,
    time_unit: str = "SUMMARY",
    client=None,
) -> str:
    """Create a Sponsored Products report and return its report ID."""
    client = client or await get_sp_client()
    request_body = _build_report_request(
        report_type_id=report_type_id,
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
        columns=columns,
        filters=filters,
        time_unit=time_unit,
    )

    create_payload = None
    report_id = None
    try:
        create_response = await client.post(
            "/reporting/reports",
            json=request_body,
            headers={
                "Content-Type": SP_CREATE_REPORT_MEDIA_TYPE,
                "Accept": "application/json",
            },
        )
        create_response.raise_for_status()
        create_payload = create_response.json()
    except httpx.HTTPError as exc:
        response = exc.response
        if response is not None and response.status_code == 425:
            duplicate_text = getattr(create_response, "text", "") or response.text
            match = REPORT_ID_PATTERN.search(duplicate_text)
            if match:
                report_id = match.group(1)
            else:
                raise _build_http_error(
                    "Sponsored Products report creation failed.", exc
                ) from exc
        else:
            raise _build_http_error(
                "Sponsored Products report creation failed.", exc
            ) from exc

    if isinstance(create_payload, dict):
        report_id = create_payload.get("reportId")
    if not report_id:
        raise SPReportError(
            "Sponsored Products report creation did not return a reportId."
        )
    return str(report_id)


async def fetch_sp_report_status(report_id: str, *, client=None) -> dict[str, Any]:
    """Fetch and normalize the current report lifecycle status."""
    client = client or await get_sp_client()
    try:
        status_response = await client.get(f"/reporting/reports/{report_id}")
        status_response.raise_for_status()
        status_payload = status_response.json()
    except httpx.HTTPError as exc:
        raise _build_http_error(
            f"Sponsored Products report {report_id} status lookup failed.", exc
        ) from exc

    if not isinstance(status_payload, dict):
        raise SPReportError(
            f"Sponsored Products report {report_id} returned an invalid status payload."
        )

    return _normalize_status_payload(str(report_id), status_payload)


async def wait_for_sp_report(
    report_id: str,
    *,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    max_poll_interval_seconds: float = MAX_POLL_INTERVAL_SECONDS,
    poll_jitter_seconds: float = DEFAULT_POLL_JITTER_SECONDS,
    timeout_seconds: float = 30.0,
    client=None,
    sleep_func=asyncio.sleep,
    monotonic_func=time.monotonic,
    jitter_func=random.uniform,
) -> dict[str, Any]:
    """Poll a Sponsored Products report until it completes or times out."""
    client = client or await get_sp_client()
    current_delay = max(poll_interval_seconds, MIN_POLL_INTERVAL_SECONDS)
    max_delay = max(max_poll_interval_seconds, MIN_POLL_INTERVAL_SECONDS)
    jitter_window = max(poll_jitter_seconds, 0.0)
    start_time = monotonic_func()
    deadline = start_time + max(timeout_seconds, 0.0)
    last_status = None

    while True:
        try:
            status = await fetch_sp_report_status(report_id, client=client)
        except SPReportError as exc:
            if last_status is None:
                raise
            elapsed = max(monotonic_func() - start_time, 0.0)
            raise SPReportError(
                f"Sponsored Products report {report_id} status lookup failed after "
                f"{_format_poll_duration(elapsed)} "
                f"(last status: {last_status['status']})."
            ) from exc

        last_status = status
        now = monotonic_func()
        elapsed = max(now - start_time, 0.0)
        if status["status"] == "COMPLETED":
            return {**status, "poll_duration_seconds": elapsed}
        if status["status"] in {"FAILED", "CANCELLED"}:
            raise SPReportError(_format_terminal_status_message(report_id, status, elapsed))
        if now >= deadline:
            raise SPReportError(_format_timeout_message(report_id, status, elapsed))

        delay = min(current_delay, max_delay)
        if jitter_window > 0:
            delay += jitter_func(-jitter_window, jitter_window)
        delay = min(max(delay, MIN_POLL_INTERVAL_SECONDS), max_delay)

        remaining = max(deadline - now, 0.0)
        if remaining <= 0:
            raise SPReportError(_format_timeout_message(report_id, status, elapsed))

        await sleep_func(min(delay, remaining))
        current_delay = min(current_delay * POLL_BACKOFF_FACTOR, max_delay)


async def download_sp_report_rows(
    report_id: str,
    *,
    status: dict[str, Any] | None = None,
    client=None,
) -> list[dict[str, Any]]:
    """Download and parse rows for a completed Sponsored Products report."""
    client = client or await get_sp_client()
    report_status = status or await fetch_sp_report_status(report_id, client=client)
    if report_status["status"] != "COMPLETED":
        if report_status["status"] in {"FAILED", "CANCELLED"}:
            raise SPReportError(
                _format_terminal_status_message(report_id, report_status, 0.0)
            )
        raise SPReportError(_format_not_ready_message(report_id, report_status))

    download_url = report_status.get("download_url")
    if not download_url:
        raise SPReportError(
            f"Sponsored Products report {report_id} completed without a download URL."
        )

    try:
        download_response = await client.get(download_url)
        download_response.raise_for_status()
    except httpx.HTTPError as exc:
        raise _build_http_error(
            f"Sponsored Products report {report_id} download failed.", exc
        ) from exc

    return _parse_report_rows(download_response.content)


async def resume_sp_report(report_id: str, *, client=None) -> dict[str, Any]:
    """Resume a known Sponsored Products report from its existing report ID."""
    client = client or await get_sp_client()
    status = await fetch_sp_report_status(report_id, client=client)
    rows = await download_sp_report_rows(report_id, status=status, client=client)
    return {"report_id": str(report_id), "rows": rows}


async def run_sp_report(
    *,
    report_type_id: str,
    start_date: str,
    end_date: str,
    group_by: list[str],
    columns: list[str],
    filters: list[dict[str, Any]] | None = None,
    time_unit: str = "SUMMARY",
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    timeout_seconds: float = 30.0,
    client=None,
) -> dict[str, Any]:
    """Run a Sponsored Products report end-to-end and return parsed rows."""
    client = client or await get_sp_client()
    report_id = await create_sp_report(
        report_type_id=report_type_id,
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
        columns=columns,
        filters=filters,
        time_unit=time_unit,
        client=client,
    )
    status = await wait_for_sp_report(
        report_id,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
        client=client,
    )
    rows = await download_sp_report_rows(report_id, status=status, client=client)
    return {"report_id": report_id, "rows": rows}
