"""Internal async report orchestration for Sponsored Products tools."""

from __future__ import annotations

import asyncio
import gzip
import json
import time
from typing import Any

import httpx

from .common import get_sp_client


class SPReportError(RuntimeError):
    """Raised when the Sponsored Products report lifecycle fails."""


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
        "name": f"{report_type_id}-{start_date}-{end_date}",
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


async def run_sp_report(
    *,
    report_type_id: str,
    start_date: str,
    end_date: str,
    group_by: list[str],
    columns: list[str],
    filters: list[dict[str, Any]] | None = None,
    time_unit: str = "SUMMARY",
    poll_interval_seconds: float = 0.0,
    timeout_seconds: float = 30.0,
    client=None,
) -> dict[str, Any]:
    """Run a Sponsored Products report end-to-end and return parsed rows."""
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

    try:
        create_response = await client.post("/reporting/reports", json=request_body)
        create_response.raise_for_status()
        create_payload = create_response.json()
    except httpx.HTTPError as exc:
        raise SPReportError("Sponsored Products report creation failed.") from exc

    report_id = None
    if isinstance(create_payload, dict):
        report_id = create_payload.get("reportId")
    if not report_id:
        raise SPReportError(
            "Sponsored Products report creation did not return a reportId."
        )

    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        try:
            status_response = await client.get(f"/reporting/reports/{report_id}")
            status_response.raise_for_status()
            status_payload = status_response.json()
        except httpx.HTTPError as exc:
            raise SPReportError(
                f"Sponsored Products report {report_id} polling failed."
            ) from exc

        if not isinstance(status_payload, dict):
            raise SPReportError(
                f"Sponsored Products report {report_id} returned an invalid status payload."
            )

        status = str(status_payload.get("status", "")).upper()
        if status in {"COMPLETED", "SUCCESS"}:
            download_url = status_payload.get("url") or status_payload.get("location")
            if not download_url:
                raise SPReportError(
                    f"Sponsored Products report {report_id} completed without a download URL."
                )

            try:
                download_response = await client.get(download_url)
                download_response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SPReportError(
                    f"Sponsored Products report {report_id} download failed."
                ) from exc

            return {
                "report_id": str(report_id),
                "rows": _parse_report_rows(download_response.content),
            }

        if status in {"FAILURE", "FAILED", "CANCELLED"}:
            details = status_payload.get("statusDetails") or status_payload.get(
                "failureReason"
            )
            message = f"Sponsored Products report {report_id} failed"
            if details:
                message = f"{message}: {details}"
            raise SPReportError(message)

        if time.monotonic() >= deadline:
            raise SPReportError(
                f"Sponsored Products report {report_id} timed out while polling."
            )

        if poll_interval_seconds > 0:
            await asyncio.sleep(poll_interval_seconds)
