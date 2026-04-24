"""Sponsored Display report status lookup."""

from __future__ import annotations

from ...models.sd_models import SDReportStatusResponse
from .common import get_sd_client, require_sd_context
from .report_helper import fetch_sd_report_status


async def get_sd_report_status(report_id: str) -> dict[str, object]:
    """Return normalized lifecycle details for an existing SD report."""
    auth_manager, profile_id, region = require_sd_context()
    client = await get_sd_client(auth_manager)
    status = await fetch_sd_report_status(report_id, client=client)
    response = SDReportStatusResponse(
        profile_id=profile_id,
        region=region,
        report_id=status["report_id"],
        status=status["status"],
        raw_status=status.get("raw_status"),
        status_details=status.get("status_details"),
        generated_at=status.get("generated_at"),
        updated_at=status.get("updated_at"),
        url_expires_at=status.get("url_expires_at"),
        download_url=status.get("download_url"),
        resume_from_report_id=status["report_id"]
        if status["status"] == "COMPLETED"
        else None,
    )
    return response.model_dump(mode="json")
