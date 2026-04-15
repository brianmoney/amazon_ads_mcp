"""Sponsored Products keyword bid updates."""

from __future__ import annotations

from typing import Any

from .common import parse_number
from .write_common import (
    SP_KEYWORD_MEDIA_TYPE,
    build_mutation_response,
    build_result,
    chunked,
    extract_error_message,
    extract_mutation_items,
    get_item_identifier,
    get_sp_write_context,
    index_items_by,
    is_success_result,
    list_keywords,
    normalize_adjustment_requests,
    sp_put,
)


SUCCESS_CODES = {"SUCCESS", "UPDATED"}


async def adjust_keyword_bids(adjustments: list[dict[str, Any]]) -> dict[str, Any]:
    """Adjust Sponsored Products keyword bids with audit context."""
    normalized_adjustments = normalize_adjustment_requests(adjustments)
    _, profile_id, region, client = await get_sp_write_context()

    requested_ids = [item["keyword_id"] for item in normalized_adjustments]
    preflight_items = await list_keywords(client, keyword_ids=requested_ids)
    preflight_index = index_items_by(preflight_items, ("keywordId",))

    results = []
    actionable = []
    for item in normalized_adjustments:
        current = preflight_index.get(item["keyword_id"])
        if current is None:
            results.append(
                build_result(
                    "failed",
                    "NOT_FOUND",
                    keyword_id=item["keyword_id"],
                    requested_bid=item["new_bid"],
                    reason=item["reason"],
                    error="Keyword was not found during preflight lookup",
                )
            )
            continue

        actionable.append((item, current))

    for batch in chunked([item for item, _ in actionable]):
        response = await sp_put(
            client,
            "/sp/keywords",
            {
                "keywords": [
                    {"keywordId": item["keyword_id"], "bid": item["new_bid"]}
                    for item in batch
                ]
            },
            SP_KEYWORD_MEDIA_TYPE,
        )
        response.raise_for_status()
        payload = response.json()
        api_items = extract_mutation_items(payload, "keywords")
        api_index = index_items_by(api_items, ("keywordId",))

        for item in batch:
            current = preflight_index[item["keyword_id"]]
            api_result = api_index.get(item["keyword_id"])
            if api_result is None and api_items:
                results.append(
                    build_result(
                        "failed",
                        "MISSING_RESULT",
                        keyword_id=item["keyword_id"],
                        keyword_text=current.get("keywordText"),
                        requested_bid=item["new_bid"],
                        previous_bid=parse_number(current.get("bid")),
                        reason=item["reason"],
                        error="Mutation response did not include this keyword",
                    )
                )
                continue

            if api_result is None or is_success_result(api_result, SUCCESS_CODES):
                resulting_bid = (
                    parse_number((api_result or {}).get("bid")) or item["new_bid"]
                )
                results.append(
                    build_result(
                        "applied",
                        "UPDATED",
                        keyword_id=item["keyword_id"],
                        keyword_text=current.get("keywordText"),
                        requested_bid=item["new_bid"],
                        previous_bid=parse_number(current.get("bid")),
                        resulting_bid=resulting_bid,
                        reason=item["reason"],
                    )
                )
                continue

            results.append(
                build_result(
                    "failed",
                    get_item_identifier(api_result, ("code", "status")) or "ERROR",
                    keyword_id=item["keyword_id"],
                    keyword_text=current.get("keywordText"),
                    requested_bid=item["new_bid"],
                    previous_bid=parse_number(current.get("bid")),
                    reason=item["reason"],
                    error=extract_error_message(api_result)
                    or "Bid update was rejected by the API",
                )
            )

    return build_mutation_response(profile_id, region, results)
