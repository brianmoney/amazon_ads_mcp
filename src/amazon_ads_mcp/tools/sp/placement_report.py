"""Sponsored Products placement reporting."""

from __future__ import annotations

from datetime import date
import re
from typing import Any

from .common import (
    SP_CAMPAIGN_MEDIA_TYPE,
    clamp_limit,
    extract_items,
    get_sp_client,
    normalize_id_list,
    parse_number,
    require_sp_context,
    safe_divide,
    sp_post,
)
from .report_helper import resume_sp_report, run_sp_report


DEFAULT_PLACEMENT_REPORT_TIMEOUT_SECONDS = 120.0
PLACEMENT_REPORT_COLUMNS = [
    "campaignId",
    "campaignName",
    "placementClassification",
    "impressions",
    "clicks",
    "cost",
    "sales14d",
    "purchases14d",
]
PLACEMENT_TYPE_MAP = {
    "TOP_OF_SEARCH": "top_of_search",
    "TOP_OF_SEARCH_FIRST_PAGE": "top_of_search",
    "PRODUCT_PAGE": "product_pages",
    "PRODUCT_PAGES": "product_pages",
    "DETAIL_PAGE": "product_pages",
    "DETAIL_PAGES": "product_pages",
    "REST_OF_SEARCH": "rest_of_search",
    "SITE_AMAZON_BUSINESS": "site_amazon_business",
}


def _validate_report_window(start_date: str, end_date: str) -> None:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("Placement reports require YYYY-MM-DD date inputs.") from exc

    if start > end:
        raise ValueError("Placement report start_date must be on or before end_date.")


def _normalize_placement_type(value: Any) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", str(value or "").strip().upper()).strip(
        "_"
    )
    if not normalized:
        return "unknown"
    return PLACEMENT_TYPE_MAP.get(normalized, normalized.lower())


def _matches_requested_scope(row: dict[str, Any], campaign_ids: list[str]) -> bool:
    if campaign_ids and str(row.get("campaignId", "")) not in campaign_ids:
        return False
    return True


def _extract_placement_bid_adjustments(campaign: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        campaign.get("placementBidAdjustments"),
        (
            campaign.get("optimizations", {})
            .get("bidSettings", {})
            .get("bidAdjustments", {})
            .get("placementBidAdjustments")
        ),
        campaign.get("bidding", {}).get("placementBidAdjustments"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _normalize_multiplier_context(campaign: dict[str, Any]) -> dict[str, float | None]:
    context = {
        "current_top_of_search_multiplier": None,
        "current_product_pages_multiplier": None,
    }

    for adjustment in _extract_placement_bid_adjustments(campaign):
        placement_type = _normalize_placement_type(adjustment.get("placement"))
        if placement_type == "top_of_search":
            context["current_top_of_search_multiplier"] = parse_number(
                adjustment.get("percentage")
            )
        if placement_type == "product_pages":
            context["current_product_pages_multiplier"] = parse_number(
                adjustment.get("percentage")
            )

    return context


async def _fetch_campaign_multiplier_context(
    client, campaign_ids: list[str]
) -> dict[str, dict[str, float | None]]:
    if not campaign_ids:
        return {}

    response = await sp_post(
        client,
        "/sp/campaigns/list",
        {
            "count": clamp_limit(len(campaign_ids), default=100),
            "campaignIdFilter": campaign_ids,
        },
        SP_CAMPAIGN_MEDIA_TYPE,
    )
    response.raise_for_status()

    contexts = {}
    for campaign in extract_items(response.json(), "campaigns"):
        campaign_id = campaign.get("campaignId")
        if campaign_id is None:
            continue
        contexts[str(campaign_id)] = _normalize_multiplier_context(campaign)
    return contexts


def _normalize_placement_row(
    row: dict[str, Any], campaign_context: dict[str, dict[str, float | None]]
) -> dict[str, Any]:
    campaign_id = str(row.get("campaignId", ""))
    impressions = parse_number(row.get("impressions"))
    clicks = parse_number(row.get("clicks"))
    spend = parse_number(row.get("cost") or row.get("spend"))
    sales = parse_number(row.get("sales14d"))
    purchases = parse_number(row.get("purchases14d") or row.get("orders14d"))
    multiplier_context = campaign_context.get(campaign_id, {})

    return {
        "campaign_id": campaign_id,
        "campaign_name": row.get("campaignName"),
        "placement_type": _normalize_placement_type(
            row.get("placementClassification")
            or row.get("placementType")
            or row.get("campaignPlacement")
            or row.get("placement")
        ),
        "impressions": impressions,
        "clicks": clicks,
        "spend": spend,
        "sales14d": sales,
        "purchases14d": purchases,
        "ctr": safe_divide(clicks, impressions),
        "cpc": safe_divide(spend, clicks),
        "acos": safe_divide(spend, sales),
        "roas": safe_divide(sales, spend),
        "current_top_of_search_multiplier": multiplier_context.get(
            "current_top_of_search_multiplier"
        ),
        "current_product_pages_multiplier": multiplier_context.get(
            "current_product_pages_multiplier"
        ),
    }


async def get_placement_report(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    limit: int = 100,
    resume_from_report_id: str | None = None,
    timeout_seconds: float = DEFAULT_PLACEMENT_REPORT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Return normalized placement performance rows with placement modifiers."""
    _validate_report_window(start_date, end_date)

    auth_manager, profile_id, region = require_sp_context()
    client = await get_sp_client(auth_manager)

    normalized_campaign_ids = normalize_id_list(campaign_ids)
    if resume_from_report_id:
        report = await resume_sp_report(resume_from_report_id, client=client)
    else:
        # Amazon exposes SP placement breakdowns through spCampaigns grouped by campaignPlacement.
        report = await run_sp_report(
            report_type_id="spCampaigns",
            start_date=start_date,
            end_date=end_date,
            group_by=["campaign", "campaignPlacement"],
            columns=PLACEMENT_REPORT_COLUMNS,
            timeout_seconds=timeout_seconds,
            client=client,
        )

    bounded_limit = clamp_limit(limit, default=100)
    filtered_rows = [
        row
        for row in report["rows"]
        if _matches_requested_scope(row, normalized_campaign_ids)
    ]
    limited_rows = filtered_rows[:bounded_limit]
    report_campaign_ids = sorted(
        {
            str(row.get("campaignId"))
            for row in limited_rows
            if row.get("campaignId") is not None
        }
    )

    campaign_context = {}
    try:
        campaign_context = await _fetch_campaign_multiplier_context(
            client, report_campaign_ids
        )
    except Exception:
        campaign_context = {}

    rows = [
        _normalize_placement_row(row, campaign_context)
        for row in limited_rows
    ]

    return {
        "profile_id": profile_id,
        "region": region,
        "start_date": start_date,
        "end_date": end_date,
        "report_id": report["report_id"],
        "filters": {
            "campaign_ids": normalized_campaign_ids,
            "limit": bounded_limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
        "rows": rows,
        "returned_count": len(rows),
    }
