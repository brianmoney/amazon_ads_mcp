"""Sponsored Products search-term reporting."""

from __future__ import annotations

from typing import Any

from .common import (
    clamp_limit,
    extract_items,
    get_sp_client,
    normalize_id_list,
    normalize_term,
    parse_number,
    require_sp_context,
)
from .report_helper import run_sp_report


SEARCH_TERM_REPORT_COLUMNS = [
    "campaignId",
    "campaignName",
    "adGroupId",
    "adGroupName",
    "searchTerm",
    "keywordId",
    "matchType",
    "impressions",
    "clicks",
    "cost",
    "sales14d",
    "orders14d",
]


def _extract_target_term(item: dict[str, Any]) -> str:
    for key in ("keywordText", "searchTerm", "resolvedExpression"):
        value = item.get(key)
        if value:
            return normalize_term(value)

    expression = item.get("expression")
    if isinstance(expression, list):
        values = [entry.get("value") for entry in expression if isinstance(entry, dict)]
        return normalize_term(" ".join(str(value) for value in values if value))

    return ""


async def _fetch_target_index(
    client, path: str, campaign_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    payload: dict[str, Any] = {"count": 100}
    if campaign_ids:
        payload["campaignIdFilter"] = campaign_ids

    response = await client.post(path, json=payload)
    response.raise_for_status()
    items = extract_items(response.json(), "targets")
    if not items:
        items = extract_items(response.json(), "negativeTargets")

    index: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        term = _extract_target_term(item)
        if term:
            index.setdefault(term, []).append(item)
    return index


def _normalize_search_term_row(
    row: dict[str, Any],
    manual_targets: dict[str, list[dict[str, Any]]],
    negative_targets: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    normalized_search_term = normalize_term(row.get("searchTerm"))
    manual_matches = manual_targets.get(normalized_search_term, [])
    negative_matches = negative_targets.get(normalized_search_term, [])

    return {
        "campaign_id": str(row.get("campaignId", "")),
        "campaign_name": row.get("campaignName"),
        "ad_group_id": str(row.get("adGroupId", "")),
        "ad_group_name": row.get("adGroupName"),
        "keyword_id": str(row.get("keywordId", "")),
        "search_term": row.get("searchTerm"),
        "match_type": row.get("matchType"),
        "impressions": parse_number(row.get("impressions")),
        "clicks": parse_number(row.get("clicks")),
        "spend": parse_number(row.get("cost")),
        "sales": parse_number(row.get("sales14d")),
        "orders": parse_number(row.get("orders14d")),
        "manually_targeted": bool(manual_matches),
        "manual_target_ids": [str(item.get("targetId", "")) for item in manual_matches],
        "negated": bool(negative_matches),
        "negative_target_ids": [
            str(item.get("targetId", "")) for item in negative_matches
        ],
        "negative_match_types": [
            item.get("matchType") for item in negative_matches if item.get("matchType")
        ],
    }


async def get_search_term_report(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Return normalized search-term rows with targeting annotations."""
    auth_manager, profile_id, region = require_sp_context()
    client = await get_sp_client(auth_manager)

    normalized_campaign_ids = normalize_id_list(campaign_ids)
    filters = []
    if normalized_campaign_ids:
        filters.append({"field": "campaignId", "values": normalized_campaign_ids})

    report = await run_sp_report(
        report_type_id="spSearchTerm",
        start_date=start_date,
        end_date=end_date,
        group_by=["searchTerm"],
        columns=SEARCH_TERM_REPORT_COLUMNS,
        filters=filters,
        client=client,
    )

    report_campaign_ids = {
        str(row.get("campaignId"))
        for row in report["rows"]
        if row.get("campaignId") is not None
    }
    target_campaign_ids = normalized_campaign_ids or sorted(report_campaign_ids)
    manual_targets = await _fetch_target_index(
        client, "/sp/targets/list", target_campaign_ids
    )
    negative_targets = await _fetch_target_index(
        client,
        "/sp/negativeTargets/list",
        target_campaign_ids,
    )

    bounded_limit = clamp_limit(limit, default=100)
    rows = [
        _normalize_search_term_row(row, manual_targets, negative_targets)
        for row in report["rows"][:bounded_limit]
    ]

    return {
        "profile_id": profile_id,
        "region": region,
        "start_date": start_date,
        "end_date": end_date,
        "report_id": report["report_id"],
        "filters": {
            "campaign_ids": target_campaign_ids,
            "limit": bounded_limit,
        },
        "rows": rows,
        "returned_count": len(rows),
    }
