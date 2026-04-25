"""Sponsored Display tool registration hooks."""

from __future__ import annotations

from typing import Annotated, Optional

from fastmcp import Context, FastMCP
from pydantic import Field

from .list_campaigns import list_sd_campaigns
from .performance import get_sd_performance
from .report_status import get_sd_report_status


_SD_REPORT_TIMEOUT_TEXT = (
    "Server-side polling timeout for this call only. Preserve the returned "
    "report_id and resume later with resume_from_report_id instead of "
    "creating a duplicate report."
)
_SD_REPORT_RESUME_TEXT = (
    "Known Sponsored Display report_id to resume instead of creating a new "
    "report."
)


async def register_all_sd_tools(server: FastMCP) -> None:
    """Register the current Sponsored Display tool surface."""

    @server.tool(
        name="list_sd_campaigns",
        description=(
            "List Sponsored Display campaigns with targeting-group context. "
            "campaign_states and objectives are normalized to uppercase when "
            "provided."
        ),
    )
    async def list_sd_campaigns_tool(
        ctx: Context,
        campaign_states: Annotated[
            Optional[list[str]],
            Field(
                default=None,
                description="Optional Sponsored Display campaign states; values are normalized to uppercase.",
            ),
        ] = None,
        campaign_ids: Annotated[
            Optional[list[str]],
            Field(default=None, description="Optional list of campaign IDs to include."),
        ] = None,
        objectives: Annotated[
            Optional[list[str]],
            Field(
                default=None,
                description="Optional campaign objectives to include; values are normalized to uppercase.",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of Sponsored Display campaigns to return."),
        ] = 25,
        offset: Annotated[
            int,
            Field(description="Zero-based page offset for the campaign listing."),
        ] = 0,
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
        description=(
            "Run or resume the Sponsored Display targeting-group performance "
            "report with derived metrics. Keep the returned report_id and resume "
            "with resume_from_report_id if polling times out."
        ),
    )
    async def get_sd_performance_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Annotated[
            Optional[list[str]],
            Field(default=None, description="Optional campaign IDs to include."),
        ] = None,
        targeting_group_ids: Annotated[
            Optional[list[str]],
            Field(default=None, description="Optional targeting group IDs to include."),
        ] = None,
        objectives: Annotated[
            Optional[list[str]],
            Field(
                default=None,
                description="Optional objectives to include; values are normalized to uppercase.",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of normalized performance rows to return."),
        ] = 100,
        resume_from_report_id: Annotated[
            Optional[str],
            Field(default=None, description=_SD_REPORT_RESUME_TEXT),
        ] = None,
        timeout_seconds: Annotated[
            float,
            Field(description=_SD_REPORT_TIMEOUT_TEXT),
        ] = 360.0,
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

    @server.tool(
        name="sd_report_status",
        description=(
            "Check Sponsored Display async report lifecycle status for a known "
            "report_id before resuming get_sd_performance."
        ),
    )
    async def sd_report_status_tool(
        ctx: Context,
        report_id: Annotated[
            str,
            Field(description="Known Sponsored Display report_id returned by get_sd_performance."),
        ],
    ) -> dict:
        return await get_sd_report_status(report_id=report_id)
