"""Sponsored Products keyword performance reporting."""

from __future__ import annotations

from typing import Any

from .common import (
    SP_KEYWORD_MEDIA_TYPE,
    clamp_limit,
    extract_items,
    get_sp_client,
    normalize_id_list,
    parse_number,
    require_sp_context,
    safe_divide,
    sp_post,
)
from .report_helper import run_sp_report


KEYWORD_REPORT_COLUMNS = [
    "campaignId",
    "campaignName",
    "adGroupId",
    "adGroupName",
    "keywordId",
    "keywordText",
    "matchType",
    "impressions",
    "clicks",
    "cost",
    "sales14d",
    "orders14d",
]


def _build_filters(
    campaign_ids: list[str],
    ad_group_ids: list[str],
    keyword_ids: list[str],
) -> list[dict[str, Any]]:
    filters = []
    if campaign_ids:
        filters.append({"field": "campaignId", "values": campaign_ids})
    if ad_group_ids:
        filters.append({"field": "adGroupId", "values": ad_group_ids})
    if keyword_ids:
        filters.append({"field": "keywordId", "values": keyword_ids})
    return filters


async def _fetch_keyword_bids(
    client,
    campaign_ids: list[str],
    ad_group_ids: list[str],
    keyword_ids: list[str],
) -> dict[str, float | None]:
    payload: dict[str, Any] = {
        "count": clamp_limit(len(keyword_ids) or 100, default=100)
    }
    if campaign_ids:
        payload["campaignIdFilter"] = campaign_ids
    if ad_group_ids:
        payload["adGroupIdFilter"] = ad_group_ids
    if keyword_ids:
        payload["keywordIdFilter"] = keyword_ids

    response = await sp_post(
        client, "/sp/keywords/list", payload, SP_KEYWORD_MEDIA_TYPE
    )
    response.raise_for_status()

    bids = {}
    for item in extract_items(response.json(), "keywords"):
        keyword_id = item.get("keywordId")
        if keyword_id is not None:
            bids[str(keyword_id)] = parse_number(item.get("bid"))
    return bids


def _normalize_keyword_row(
    row: dict[str, Any], keyword_bids: dict[str, float | None]
) -> dict[str, Any]:
    keyword_id = str(row.get("keywordId", ""))
    impressions = parse_number(row.get("impressions"))
    clicks = parse_number(row.get("clicks"))
    spend = parse_number(row.get("cost"))
    sales = parse_number(row.get("sales14d"))
    orders = parse_number(row.get("orders14d"))

    return {
        "campaign_id": str(row.get("campaignId", "")),
        "campaign_name": row.get("campaignName"),
        "ad_group_id": str(row.get("adGroupId", "")),
        "ad_group_name": row.get("adGroupName"),
        "keyword_id": keyword_id,
        "keyword_text": row.get("keywordText") or row.get("keyword"),
        "match_type": row.get("matchType"),
        "bid": keyword_bids.get(keyword_id),
        "impressions": impressions,
        "clicks": clicks,
        "spend": spend,
        "sales": sales,
        "orders": orders,
        "ctr": safe_divide(clicks, impressions),
        "cpc": safe_divide(spend, clicks),
        "acos": safe_divide(spend, sales),
        "roas": safe_divide(sales, spend),
    }


async def get_keyword_performance(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    ad_group_ids: list[str] | None = None,
    keyword_ids: list[str] | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Return normalized keyword performance rows with bid context."""
    auth_manager, profile_id, region = require_sp_context()
    client = await get_sp_client(auth_manager)

    normalized_campaign_ids = normalize_id_list(campaign_ids)
    normalized_ad_group_ids = normalize_id_list(ad_group_ids)
    normalized_keyword_ids = normalize_id_list(keyword_ids)
    filters = _build_filters(
        normalized_campaign_ids,
        normalized_ad_group_ids,
        normalized_keyword_ids,
    )

    report = await run_sp_report(
        report_type_id="spKeyword",
        start_date=start_date,
        end_date=end_date,
        group_by=["keyword"],
        columns=KEYWORD_REPORT_COLUMNS,
        filters=filters,
        client=client,
    )
    keyword_bids = await _fetch_keyword_bids(
        client,
        normalized_campaign_ids,
        normalized_ad_group_ids,
        normalized_keyword_ids,
    )

    bounded_limit = clamp_limit(limit, default=100)
    rows = [
        _normalize_keyword_row(row, keyword_bids)
        for row in report["rows"][:bounded_limit]
    ]

    return {
        "profile_id": profile_id,
        "region": region,
        "start_date": start_date,
        "end_date": end_date,
        "report_id": report["report_id"],
        "filters": {
            "campaign_ids": normalized_campaign_ids,
            "ad_group_ids": normalized_ad_group_ids,
            "keyword_ids": normalized_keyword_ids,
            "limit": bounded_limit,
        },
        "rows": rows,
        "returned_count": len(rows),
    }
