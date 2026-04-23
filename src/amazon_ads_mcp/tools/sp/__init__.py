"""Sponsored Products tool registration hooks."""

from __future__ import annotations

from typing import Any, Optional

from fastmcp import Context, FastMCP

from .add_keywords import add_keywords
from .adjust_keyword_bids import adjust_keyword_bids
from .campaign_budget_history import get_campaign_budget_history
from .keyword_performance import get_keyword_performance
from .list_campaigns import list_campaigns
from .negate_keywords import negate_keywords
from .pause_keywords import pause_keywords
from .placement_report import get_placement_report
from .report_status import get_sp_report_status
from .search_term_report import get_search_term_report
from .update_campaign_budget import update_campaign_budget


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
        name="get_campaign_budget_history",
        description="Get Sponsored Products daily budget history with utilization context",
    )
    async def get_campaign_budget_history_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Optional[list[str]] = None,
        limit: int = 100,
        resume_from_report_id: Optional[str] = None,
        timeout_seconds: float = 120.0,
    ) -> dict:
        return await get_campaign_budget_history(
            start_date=start_date,
            end_date=end_date,
            campaign_ids=campaign_ids,
            limit=limit,
            resume_from_report_id=resume_from_report_id,
            timeout_seconds=timeout_seconds,
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
        resume_from_report_id: Optional[str] = None,
        timeout_seconds: float = 360.0,
    ) -> dict:
        return await get_keyword_performance(
            start_date=start_date,
            end_date=end_date,
            campaign_ids=campaign_ids,
            ad_group_ids=ad_group_ids,
            keyword_ids=keyword_ids,
            limit=limit,
            resume_from_report_id=resume_from_report_id,
            timeout_seconds=timeout_seconds,
        )

    @server.tool(
        name="get_placement_report",
        description="Get Sponsored Products placement performance with current placement multipliers",
    )
    async def get_placement_report_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Optional[list[str]] = None,
        limit: int = 100,
        resume_from_report_id: Optional[str] = None,
        timeout_seconds: float = 120.0,
    ) -> dict:
        return await get_placement_report(
            start_date=start_date,
            end_date=end_date,
            campaign_ids=campaign_ids,
            limit=limit,
            resume_from_report_id=resume_from_report_id,
            timeout_seconds=timeout_seconds,
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
        resume_from_report_id: Optional[str] = None,
        timeout_seconds: float = 120.0,
    ) -> dict:
        return await get_search_term_report(
            start_date=start_date,
            end_date=end_date,
            campaign_ids=campaign_ids,
            limit=limit,
            resume_from_report_id=resume_from_report_id,
            timeout_seconds=timeout_seconds,
        )

    @server.tool(
        name="sp_report_status",
        description="Check Sponsored Products report lifecycle status for a known report ID",
    )
    async def sp_report_status_tool(ctx: Context, report_id: str) -> dict:
        return await get_sp_report_status(report_id=report_id)

    @server.tool(
        name="adjust_keyword_bids",
        description="Adjust Sponsored Products keyword bids with audit details",
    )
    async def adjust_keyword_bids_tool(
        ctx: Context,
        adjustments: list[dict[str, Any]],
    ) -> dict:
        return await adjust_keyword_bids(adjustments=adjustments)

    @server.tool(
        name="add_keywords",
        description="Create Sponsored Products keywords with duplicate detection",
    )
    async def add_keywords_tool(
        ctx: Context,
        campaign_id: str,
        ad_group_id: str,
        keywords: list[dict[str, Any]],
    ) -> dict:
        return await add_keywords(
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            keywords=keywords,
        )

    @server.tool(
        name="negate_keywords",
        description="Create negative exact Sponsored Products keywords",
    )
    async def negate_keywords_tool(
        ctx: Context,
        campaign_id: str,
        keywords: list[str],
        ad_group_id: Optional[str] = None,
    ) -> dict:
        return await negate_keywords(
            campaign_id=campaign_id,
            keywords=keywords,
            ad_group_id=ad_group_id,
        )

    @server.tool(
        name="pause_keywords",
        description="Pause Sponsored Products keywords with no-op detection",
    )
    async def pause_keywords_tool(
        ctx: Context,
        keyword_ids: list[str],
        reason: Optional[str] = None,
    ) -> dict:
        return await pause_keywords(keyword_ids=keyword_ids, reason=reason)

    @server.tool(
        name="update_campaign_budget",
        description="Update a Sponsored Products campaign daily budget with audit details",
    )
    async def update_campaign_budget_tool(
        ctx: Context,
        campaign_id: str,
        daily_budget: float,
    ) -> dict:
        return await update_campaign_budget(
            campaign_id=campaign_id,
            daily_budget=daily_budget,
        )
