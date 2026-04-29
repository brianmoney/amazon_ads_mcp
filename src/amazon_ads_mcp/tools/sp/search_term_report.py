"""Sponsored Products search-term reporting."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .common import (
    SP_NEGATIVE_TARGET_MEDIA_TYPE,
    SP_TARGET_MEDIA_TYPE,
    clamp_limit,
    extract_items,
    get_sp_client,
    normalize_id_list,
    normalize_term,
    parse_number,
    require_sp_context,
    sp_post,
)
from .report_helper import resume_sp_report, run_sp_report


DEFAULT_SEARCH_TERM_TIMEOUT_SECONDS = 120.0


SEARCH_TERM_REPORT_COLUMNS = [
    "campaignId",
    "campaignName",
    "adGroupId",
    "adGroupName",
    "searchTerm",
    "keywordId",
    "keyword",
    "matchType",
    "impressions",
    "clicks",
    "cost",
    "sales14d",
    "purchases14d",
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
        payload["campaignIdFilter"] = {"include": campaign_ids}

    media_type = (
        SP_TARGET_MEDIA_TYPE
        if path == "/sp/targets/list"
        else SP_NEGATIVE_TARGET_MEDIA_TYPE
    )
    response = await sp_post(client, path, payload, media_type)
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
        "orders": parse_number(row.get("orders14d") or row.get("purchases14d")),
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


def _unique_strings(values: Iterable[Any]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _merge_search_term_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregated: dict[tuple[str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str]] = []
    for row in rows:
        key = (
            str(row.get("campaign_id", "")).strip(),
            str(row.get("ad_group_id", "")).strip(),
            normalize_term(row.get("search_term")),
        )
        existing = aggregated.get(key)
        if existing is None:
            keyword_ids = _unique_strings([row.get("keyword_id")])
            aggregated[key] = {
                **row,
                "keyword_ids": keyword_ids,
                "keyword_id": keyword_ids[0] if len(keyword_ids) == 1 else "",
                "manual_target_ids": _unique_strings(row.get("manual_target_ids") or []),
                "negative_target_ids": _unique_strings(
                    row.get("negative_target_ids") or []
                ),
                "negative_match_types": _unique_strings(
                    row.get("negative_match_types") or []
                ),
            }
            order.append(key)
            continue

        keyword_ids = _unique_strings(
            [*(existing.get("keyword_ids") or []), row.get("keyword_id")]
        )
        existing["keyword_ids"] = keyword_ids
        existing["keyword_id"] = keyword_ids[0] if len(keyword_ids) == 1 else ""

        search_term = row.get("search_term")
        if search_term and not existing.get("search_term"):
            existing["search_term"] = search_term

        match_type = row.get("match_type")
        if match_type and not existing.get("match_type"):
            existing["match_type"] = match_type
        elif match_type and existing.get("match_type") != match_type:
            existing["match_type"] = None

        for metric in ("impressions", "clicks", "spend", "sales", "orders"):
            existing[metric] = (existing.get(metric) or 0) + (row.get(metric) or 0)

        existing["manually_targeted"] = bool(
            existing.get("manually_targeted") or row.get("manually_targeted")
        )
        existing["negated"] = bool(existing.get("negated") or row.get("negated"))
        existing["manual_target_ids"] = _unique_strings(
            [
                *(existing.get("manual_target_ids") or []),
                *(row.get("manual_target_ids") or []),
            ]
        )
        existing["negative_target_ids"] = _unique_strings(
            [
                *(existing.get("negative_target_ids") or []),
                *(row.get("negative_target_ids") or []),
            ]
        )
        existing["negative_match_types"] = _unique_strings(
            [
                *(existing.get("negative_match_types") or []),
                *(row.get("negative_match_types") or []),
            ]
        )

    return [aggregated[key] for key in order]


async def get_search_term_report(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    limit: int = 100,
    resume_from_report_id: str | None = None,
    timeout_seconds: float = DEFAULT_SEARCH_TERM_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Return normalized search-term rows with targeting annotations."""
    auth_manager, profile_id, region = require_sp_context()
    client = await get_sp_client(auth_manager)

    normalized_campaign_ids = normalize_id_list(campaign_ids)
    if resume_from_report_id:
        report = await resume_sp_report(resume_from_report_id, client=client)
    else:
        report = await run_sp_report(
            report_type_id="spSearchTerm",
            start_date=start_date,
            end_date=end_date,
            group_by=["searchTerm"],
            columns=SEARCH_TERM_REPORT_COLUMNS,
            filters=[],
            timeout_seconds=timeout_seconds,
            client=client,
        )

    report_campaign_ids = {
        str(row.get("campaignId"))
        for row in report["rows"]
        if row.get("campaignId") is not None
    }
    filtered_report_rows = [
        row
        for row in report["rows"]
        if not normalized_campaign_ids
        or str(row.get("campaignId", "")) in normalized_campaign_ids
    ]
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
    rows = _merge_search_term_rows(
        [
        _normalize_search_term_row(row, manual_targets, negative_targets)
        for row in filtered_report_rows[:bounded_limit]
        ]
    )

    return {
        "profile_id": profile_id,
        "region": region,
        "start_date": start_date,
        "end_date": end_date,
        "report_id": report["report_id"],
        "filters": {
            "campaign_ids": target_campaign_ids,
            "limit": bounded_limit,
            "resume_from_report_id": resume_from_report_id,
        },
        "rows": rows,
        "returned_count": len(rows),
    }
