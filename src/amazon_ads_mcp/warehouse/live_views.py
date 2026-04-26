"""Reusable live-runtime helpers for warehouse ingestion."""

from __future__ import annotations

from typing import Any

from ..tools.portfolio.budget_usage import get_portfolio_budget_usage
from ..tools.portfolio.list_portfolios import list_portfolios
from ..tools.profile_listing import get_profiles_cached
from ..tools.sp.campaign_budget_history import (
    get_campaign_budget_history,
)
from ..tools.sp.keyword_performance import (
    get_keyword_performance,
)
from ..tools.sp.list_campaigns import list_campaigns
from ..tools.sp.placement_report import get_placement_report
from ..tools.sp.search_term_report import get_search_term_report
from ..tools.sp.impression_share import get_impression_share_report
from ..tools.sp.report_helper import (
    create_sp_report,
    download_sp_report_rows,
    fetch_sp_report_status,
    wait_for_sp_report,
)
from ..tools.sp.write_common import list_keywords


async def fetch_live_profiles() -> list[dict[str, Any]]:
    """Return the profile list through the existing cached profile helper."""
    profiles, _ = await get_profiles_cached(force_refresh=True)
    return profiles


async def fetch_live_portfolios(
    *,
    portfolio_ids: list[str] | None = None,
    portfolio_states: list[str] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return normalized live portfolio settings."""
    payload = await list_portfolios(
        portfolio_ids=portfolio_ids,
        portfolio_states=portfolio_states,
        limit=limit,
        offset=0,
    )
    return payload["portfolios"]


async def fetch_live_campaigns(*, campaign_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Return normalized SP campaigns with nested ad groups."""
    payload = await list_campaigns(campaign_ids=campaign_ids, limit=100, offset=0)
    return payload["campaigns"]


async def fetch_live_keywords(
    *,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    keyword_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return current keyword context from the shared write helper."""
    from ..tools.sp.common import get_sp_client, require_sp_context

    auth_manager, _, _ = require_sp_context()
    client = await get_sp_client(auth_manager)
    return await list_keywords(
        client,
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        keyword_ids=keyword_ids,
    )


async def create_live_report(request, *, client):
    """Create a live Sponsored Products report without changing tool semantics."""
    return await create_sp_report(
        report_type_id=request.report_type_id,
        start_date=request.start_date,
        end_date=request.end_date,
        group_by=request.group_by,
        columns=request.columns,
        filters=request.filters,
        time_unit=request.time_unit,
        client=client,
    )


async def poll_live_report(report_id: str, *, client, timeout_seconds: float) -> dict[str, Any]:
    """Poll a live report using the shared report lifecycle."""
    return await wait_for_sp_report(
        report_id,
        timeout_seconds=timeout_seconds,
        client=client,
    )


async def lookup_live_report_status(report_id: str, *, client) -> dict[str, Any]:
    """Return the shared normalized live report status payload."""
    return await fetch_sp_report_status(report_id, client=client)


async def download_live_report_rows(report_id: str, *, client, status: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Download shared report rows from a known live report id."""
    return await download_sp_report_rows(report_id, client=client, status=status)


__all__ = [
    "create_live_report",
    "download_live_report_rows",
    "fetch_live_campaigns",
    "fetch_live_keywords",
    "fetch_live_portfolios",
    "fetch_live_profiles",
    "get_campaign_budget_history",
    "get_impression_share_report",
    "get_keyword_performance",
    "get_placement_report",
    "get_portfolio_budget_usage",
    "get_search_term_report",
    "lookup_live_report_status",
    "poll_live_report",
]
