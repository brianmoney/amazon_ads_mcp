"""Sponsored Products report status lookup."""

from __future__ import annotations

from .common import get_sp_client, require_sp_context
from .report_helper import fetch_sp_report_status


async def get_sp_report_status(report_id: str) -> dict[str, object]:
    """Return normalized lifecycle details for an existing SP report."""
    auth_manager, profile_id, region = require_sp_context()
    client = await get_sp_client(auth_manager)
    status = await fetch_sp_report_status(report_id, client=client)
    return {
        "profile_id": profile_id,
        "region": region,
        **status,
    }
