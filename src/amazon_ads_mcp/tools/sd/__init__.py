"""Sponsored Display tool registration hooks."""

from __future__ import annotations

from typing import Optional

from fastmcp import Context, FastMCP

from .list_campaigns import list_sd_campaigns
from .performance import get_sd_performance


async def register_all_sd_tools(server: FastMCP) -> None:
    """Register the current Sponsored Display tool surface."""

    @server.tool(
        name="list_sd_campaigns",
        description="List Sponsored Display campaigns with targeting-group context",
    )
    async def list_sd_campaigns_tool(
        ctx: Context,
        campaign_states: Optional[list[str]] = None,
        campaign_ids: Optional[list[str]] = None,
        objectives: Optional[list[str]] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        return await list_sd_campaigns(
            campaign_states=campaign_states,
            campaign_ids=campaign_ids,
            objectives=objectives,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        name="get_sd_performance",
        description="Get Sponsored Display targeting-group performance with derived metrics",
    )
    async def get_sd_performance_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Optional[list[str]] = None,
        targeting_group_ids: Optional[list[str]] = None,
        objectives: Optional[list[str]] = None,
        limit: int = 100,
        resume_from_report_id: Optional[str] = None,
        timeout_seconds: float = 360.0,
    ) -> dict:
        return await get_sd_performance(
            start_date=start_date,
            end_date=end_date,
            campaign_ids=campaign_ids,
            targeting_group_ids=targeting_group_ids,
            objectives=objectives,
            limit=limit,
            resume_from_report_id=resume_from_report_id,
            timeout_seconds=timeout_seconds,
        )
