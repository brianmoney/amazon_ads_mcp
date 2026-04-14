"""Sponsored Products tool registration hooks."""

from __future__ import annotations

from typing import Optional

from fastmcp import Context, FastMCP

from .keyword_performance import get_keyword_performance
from .list_campaigns import list_campaigns
from .search_term_report import get_search_term_report


async def register_all_sp_tools(server: FastMCP) -> None:
    """Register the current Sponsored Products tool surface."""

    @server.tool(
        name="list_campaigns",
        description="List Sponsored Products campaigns with nested ad groups",
    )
    async def list_campaigns_tool(
        ctx: Context,
        campaign_states: Optional[list[str]] = None,
        campaign_ids: Optional[list[str]] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        return await list_campaigns(
            campaign_states=campaign_states,
            campaign_ids=campaign_ids,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        name="get_keyword_performance",
        description="Get Sponsored Products keyword performance with derived metrics",
    )
    async def get_keyword_performance_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Optional[list[str]] = None,
        ad_group_ids: Optional[list[str]] = None,
        keyword_ids: Optional[list[str]] = None,
        limit: int = 100,
    ) -> dict:
        return await get_keyword_performance(
            start_date=start_date,
            end_date=end_date,
            campaign_ids=campaign_ids,
            ad_group_ids=ad_group_ids,
            keyword_ids=keyword_ids,
            limit=limit,
        )

    @server.tool(
        name="get_search_term_report",
        description="Get Sponsored Products search terms with manual and negative targeting context",
    )
    async def get_search_term_report_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Optional[list[str]] = None,
        limit: int = 100,
    ) -> dict:
        return await get_search_term_report(
            start_date=start_date,
            end_date=end_date,
            campaign_ids=campaign_ids,
            limit=limit,
        )
