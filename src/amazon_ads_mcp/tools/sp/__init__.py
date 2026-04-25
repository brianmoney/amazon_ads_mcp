"""Sponsored Products tool registration hooks."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from fastmcp import Context, FastMCP
from pydantic import Field

from .add_keywords import add_keywords
from .adjust_keyword_bids import adjust_keyword_bids
from .campaign_budget_history import get_campaign_budget_history
from .impression_share import get_impression_share_report
from .keyword_performance import get_keyword_performance
from .list_campaigns import list_campaigns
from .negate_keywords import negate_keywords
from .pause_keywords import pause_keywords
from .placement_report import get_placement_report
from .report_status import get_sp_report_status
from .search_term_report import get_search_term_report
from .update_campaign_budget import update_campaign_budget
from .write_common import MAX_BID, MIN_BID


_BID_RANGE_TEXT = f"{MIN_BID:.2f} to {MAX_BID:.2f}"
_SP_CAMPAIGN_STATE_TEXT = "ENABLED, PAUSED, or ARCHIVED"
# Keep timeout behavior unchanged for this metadata pass. The current report
# helpers still raise timeout errors, so a structured timeout payload needs a
# separate contract change.
_REPORT_TIMEOUT_TEXT = (
    "Server-side polling timeout for this call only. Preserve the returned "
    "report_id and resume later with resume_from_report_id instead of "
    "creating a duplicate report."
)
_REPORT_RESUME_TEXT = (
    "Known report_id to resume instead of creating a new report. Use the "
    "report_id returned by an earlier timeout or in-progress response."
)
_ADJUSTMENT_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "keyword_id": {
            "type": "string",
            "description": "Required Sponsored Products keyword identifier.",
        },
        "new_bid": {
            "type": "number",
            "description": (
                "Required bid to apply now. Must be between "
                f"{_BID_RANGE_TEXT}."
            ),
        },
        "reason": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
            "description": "Optional audit note for why this bid is changing.",
        },
    },
    "required": ["keyword_id", "new_bid"],
}
_KEYWORD_CREATE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "keyword_text": {
            "type": "string",
            "description": "Required keyword phrase to create.",
        },
        "match_type": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
            "description": (
                "Optional match type. Supported values: EXACT, PHRASE, or "
                "BROAD. Defaults to EXACT when omitted."
            ),
        },
        "bid": {
            "type": "number",
            "description": (
                "Required starting bid for the keyword. Must be between "
                f"{_BID_RANGE_TEXT}."
            ),
        },
    },
    "required": ["keyword_text", "bid"],
}


async def register_all_sp_tools(server: FastMCP) -> None:
    """Register the current Sponsored Products tool surface."""

    @server.tool(
        name="list_campaigns",
        description=(
            "List Sponsored Products campaigns with nested ad groups. "
            "campaign_states accepts ENABLED, PAUSED, or ARCHIVED, normalizes "
            "input to uppercase, and leaves state unfiltered when omitted."
        ),
    )
    async def list_campaigns_tool(
        ctx: Context,
        campaign_states: Annotated[
            Optional[list[str]],
            Field(
                default=None,
                description=(
                    "Optional campaign state filter. Accepted values: "
                    f"{_SP_CAMPAIGN_STATE_TEXT}. Values are normalized to "
                    "uppercase before the upstream request. Omit this filter "
                    "to list campaigns in any state."
                ),
            ),
        ] = None,
        campaign_ids: Annotated[
            Optional[list[str]],
            Field(
                default=None,
                description="Optional list of specific campaign IDs to include.",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of campaigns to return in this page."),
        ] = 25,
        offset: Annotated[
            int,
            Field(description="Zero-based page offset for the campaign listing."),
        ] = 0,
    ) -> dict:
        return await list_campaigns(
            campaign_states=campaign_states,
            campaign_ids=campaign_ids,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        name="get_campaign_budget_history",
        description=(
            "Run or resume the Sponsored Products budget-history report with "
            "daily utilization context. Keep the returned report_id and resume "
            "with resume_from_report_id if polling times out."
        ),
    )
    async def get_campaign_budget_history_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Annotated[
            Optional[list[str]],
            Field(
                default=None,
                description="Optional list of campaign IDs to include in the report.",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of normalized budget-history rows to return."),
        ] = 100,
        resume_from_report_id: Annotated[
            Optional[str],
            Field(default=None, description=_REPORT_RESUME_TEXT),
        ] = None,
        timeout_seconds: Annotated[
            float,
            Field(description=_REPORT_TIMEOUT_TEXT),
        ] = 120.0,
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
        name="get_impression_share_report",
        description=(
            "Run or resume the Sponsored Products top-of-search impression "
            "share report with explicit availability diagnostics. Keep the "
            "returned report_id and resume with resume_from_report_id if "
            "polling times out."
        ),
    )
    async def get_impression_share_report_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Annotated[
            Optional[list[str]],
            Field(
                default=None,
                description="Optional campaign IDs to scope the campaign-level report.",
            ),
        ] = None,
        ad_group_ids: Annotated[
            Optional[list[str]],
            Field(
                default=None,
                description=(
                    "Optional ad group IDs. The current impression-share tool "
                    "is campaign-level only, so supplying ad_group_ids returns "
                    "an explicit unsupported result."
                ),
            ),
        ] = None,
        keyword_ids: Annotated[
            Optional[list[str]],
            Field(
                default=None,
                description=(
                    "Optional keyword IDs. The current impression-share tool is "
                    "campaign-level only, so supplying keyword_ids returns an "
                    "explicit unsupported result."
                ),
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of normalized impression-share rows to return."),
        ] = 100,
        resume_from_report_id: Annotated[
            Optional[str],
            Field(default=None, description=_REPORT_RESUME_TEXT),
        ] = None,
        timeout_seconds: Annotated[
            float,
            Field(description=_REPORT_TIMEOUT_TEXT),
        ] = 120.0,
    ) -> dict:
        return await get_impression_share_report(
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
        name="get_keyword_performance",
        description=(
            "Run or resume the Sponsored Products keyword report with derived "
            "metrics. The current tool returns manual keyword rows only, so "
            "auto-targeting campaigns can legitimately return zero rows. Keep "
            "the returned report_id and resume with resume_from_report_id if "
            "polling times out."
        ),
    )
    async def get_keyword_performance_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Annotated[
            Optional[list[str]],
            Field(default=None, description="Optional campaign IDs to include."),
        ] = None,
        ad_group_ids: Annotated[
            Optional[list[str]],
            Field(default=None, description="Optional ad group IDs to include."),
        ] = None,
        keyword_ids: Annotated[
            Optional[list[str]],
            Field(default=None, description="Optional keyword IDs to include."),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of normalized keyword rows to return."),
        ] = 100,
        resume_from_report_id: Annotated[
            Optional[str],
            Field(default=None, description=_REPORT_RESUME_TEXT),
        ] = None,
        timeout_seconds: Annotated[
            float,
            Field(description=_REPORT_TIMEOUT_TEXT),
        ] = 360.0,
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
        description=(
            "Run or resume the Sponsored Products placement report with current "
            "placement multipliers. Keep the returned report_id and resume with "
            "resume_from_report_id if polling times out."
        ),
    )
    async def get_placement_report_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Annotated[
            Optional[list[str]],
            Field(default=None, description="Optional campaign IDs to include."),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of normalized placement rows to return."),
        ] = 100,
        resume_from_report_id: Annotated[
            Optional[str],
            Field(default=None, description=_REPORT_RESUME_TEXT),
        ] = None,
        timeout_seconds: Annotated[
            float,
            Field(description=_REPORT_TIMEOUT_TEXT),
        ] = 120.0,
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
        description=(
            "Run or resume the Sponsored Products search-term report with manual "
            "and negative targeting context. Keep the returned report_id and "
            "resume with resume_from_report_id if polling times out."
        ),
    )
    async def get_search_term_report_tool(
        ctx: Context,
        start_date: str,
        end_date: str,
        campaign_ids: Annotated[
            Optional[list[str]],
            Field(default=None, description="Optional campaign IDs to include."),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of normalized search-term rows to return."),
        ] = 100,
        resume_from_report_id: Annotated[
            Optional[str],
            Field(default=None, description=_REPORT_RESUME_TEXT),
        ] = None,
        timeout_seconds: Annotated[
            float,
            Field(description=_REPORT_TIMEOUT_TEXT),
        ] = 120.0,
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
        description=(
            "Check Sponsored Products async report lifecycle status for a known "
            "report_id before resuming the corresponding report tool."
        ),
    )
    async def sp_report_status_tool(
        ctx: Context,
        report_id: Annotated[
            str,
            Field(description="Known Sponsored Products report_id returned by a report tool."),
        ],
    ) -> dict:
        return await get_sp_report_status(report_id=report_id)

    @server.tool(
        name="adjust_keyword_bids",
        description=(
            "Apply batch Sponsored Products keyword bid changes with auditable "
            "before-and-after details. Each result's previous_bid or prior_bid "
            "is the live preflight bid observed at write time, not an earlier "
            "optimization snapshot."
        ),
    )
    async def adjust_keyword_bids_tool(
        ctx: Context,
        adjustments: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "Required non-empty list of bid adjustments. Each item must "
                    "match { keyword_id, new_bid, reason? }."
                ),
                json_schema_extra={"items": _ADJUSTMENT_ITEM_SCHEMA},
            ),
        ],
    ) -> dict:
        return await adjust_keyword_bids(adjustments=adjustments)

    @server.tool(
        name="add_keywords",
        description=(
            "Create Sponsored Products keywords with duplicate detection. Each "
            "keyword item must include keyword_text and bid, supports EXACT, "
            "PHRASE, or BROAD match types, and enforces the current bid bounds "
            f"of {_BID_RANGE_TEXT}."
        ),
    )
    async def add_keywords_tool(
        ctx: Context,
        campaign_id: Annotated[
            str,
            Field(description="Required campaign ID that owns the target ad group."),
        ],
        ad_group_id: Annotated[
            str,
            Field(description="Required ad group ID where the keywords will be created."),
        ],
        keywords: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "Required non-empty list of keyword objects. Each item must "
                    "match { keyword_text, bid, match_type? }."
                ),
                json_schema_extra={"items": _KEYWORD_CREATE_ITEM_SCHEMA},
            ),
        ],
    ) -> dict:
        return await add_keywords(
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            keywords=keywords,
        )

    @server.tool(
        name="negate_keywords",
        description=(
            "Create negative exact Sponsored Products keywords at the campaign "
            "or ad-group level."
        ),
    )
    async def negate_keywords_tool(
        ctx: Context,
        campaign_id: Annotated[
            str,
            Field(description="Required campaign ID for the negative keyword scope."),
        ],
        keywords: Annotated[
            list[str],
            Field(description="Required non-empty list of keyword phrases to negate."),
        ],
        ad_group_id: Annotated[
            Optional[str],
            Field(
                default=None,
                description=(
                    "Optional ad group ID. Omit it to create campaign-level "
                    "negative keywords."
                ),
            ),
        ] = None,
    ) -> dict:
        return await negate_keywords(
            campaign_id=campaign_id,
            keywords=keywords,
            ad_group_id=ad_group_id,
        )

    @server.tool(
        name="pause_keywords",
        description=(
            "Pause Sponsored Products keywords with no-op detection for already "
            "paused rows."
        ),
    )
    async def pause_keywords_tool(
        ctx: Context,
        keyword_ids: Annotated[
            list[str],
            Field(description="Required non-empty list of keyword IDs to pause."),
        ],
        reason: Annotated[
            Optional[str],
            Field(default=None, description="Optional audit note for why the keywords are being paused."),
        ] = None,
    ) -> dict:
        return await pause_keywords(keyword_ids=keyword_ids, reason=reason)

    @server.tool(
        name="update_campaign_budget",
        description=(
            "Update a Sponsored Products campaign daily budget with audit details "
            "including the observed previous budget when available."
        ),
    )
    async def update_campaign_budget_tool(
        ctx: Context,
        campaign_id: Annotated[
            str,
            Field(description="Required campaign ID to update."),
        ],
        daily_budget: Annotated[
            float,
            Field(description="Required new daily budget amount for the campaign."),
        ],
    ) -> dict:
        return await update_campaign_budget(
            campaign_id=campaign_id,
            daily_budget=daily_budget,
        )
