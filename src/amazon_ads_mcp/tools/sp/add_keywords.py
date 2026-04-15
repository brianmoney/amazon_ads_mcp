"""Sponsored Products keyword creation."""

from __future__ import annotations

from typing import Any

from .common import normalize_term, parse_number
from .write_common import (
    SP_KEYWORD_MEDIA_TYPE,
    build_lookup_key,
    build_mutation_response,
    build_result,
    chunked,
    extract_error_message,
    extract_mutation_items,
    get_sp_write_context,
    is_success_result,
    list_keywords,
    normalize_identifier,
    normalize_keyword_create_requests,
    sp_post,
)


SUCCESS_CODES = {"SUCCESS", "CREATED"}


def _response_lookup_key(item: dict[str, Any]) -> str:
    return build_lookup_key(item.get("keywordText"), item.get("matchType"))


async def add_keywords(
    campaign_id: str,
    ad_group_id: str,
    keywords: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create Sponsored Products keywords with duplicate detection."""
    normalized_campaign_id = normalize_identifier(campaign_id, "campaign_id")
    normalized_ad_group_id = normalize_identifier(ad_group_id, "ad_group_id")
    normalized_keywords = normalize_keyword_create_requests(keywords)
    _, profile_id, region, client = await get_sp_write_context()

    existing_items = await list_keywords(
        client,
        campaign_id=normalized_campaign_id,
        ad_group_id=normalized_ad_group_id,
    )
    existing_index = {
        build_lookup_key(item.get("keywordText"), item.get("matchType")): item
        for item in existing_items
        if item.get("keywordText")
    }

    results = []
    actionable = []
    for item in normalized_keywords:
        existing = existing_index.get(item["lookup_key"])
        if existing is not None:
            results.append(
                build_result(
                    "skipped",
                    "DUPLICATE",
                    keyword_text=item["keyword_text"],
                    match_type=item["match_type"],
                    bid=item["bid"],
                    existing_keyword_id=str(existing.get("keywordId", "")) or None,
                    existing_state=existing.get("state"),
                    existing_bid=parse_number(existing.get("bid")),
                )
            )
            continue
        actionable.append(item)

    for batch in chunked(actionable):
        response = await sp_post(
            client,
            "/sp/keywords",
            {
                "keywords": [
                    {
                        "campaignId": normalized_campaign_id,
                        "adGroupId": normalized_ad_group_id,
                        "keywordText": item["keyword_text"],
                        "matchType": item["match_type"],
                        "bid": item["bid"],
                        "state": "ENABLED",
                    }
                    for item in batch
                ]
            },
            SP_KEYWORD_MEDIA_TYPE,
        )
        response.raise_for_status()
        payload = response.json()
        api_items = extract_mutation_items(payload, "keywords")
        api_index = {_response_lookup_key(item): item for item in api_items}

        for item in batch:
            api_result = api_index.get(item["lookup_key"])
            if api_result is None and api_items:
                results.append(
                    build_result(
                        "failed",
                        "MISSING_RESULT",
                        keyword_text=item["keyword_text"],
                        match_type=item["match_type"],
                        bid=item["bid"],
                        error="Mutation response did not include this keyword",
                    )
                )
                continue

            if api_result is None or is_success_result(api_result, SUCCESS_CODES):
                results.append(
                    build_result(
                        "applied",
                        "CREATED",
                        keyword_text=item["keyword_text"],
                        match_type=item["match_type"],
                        bid=item["bid"],
                        keyword_id=str(api_result.get("keywordId", ""))
                        if api_result
                        else None,
                    )
                )
                continue

            results.append(
                build_result(
                    "failed",
                    (api_result.get("code") or api_result.get("status") or "ERROR"),
                    keyword_text=item["keyword_text"],
                    match_type=item["match_type"],
                    bid=item["bid"],
                    error=extract_error_message(api_result)
                    or "Keyword create request was rejected",
                )
            )

    results.sort(
        key=lambda item: (
            normalize_term(item.get("keyword_text")),
            str(item.get("match_type") or ""),
        )
    )
    return build_mutation_response(
        profile_id,
        region,
        results,
        campaign_id=normalized_campaign_id,
        ad_group_id=normalized_ad_group_id,
    )
