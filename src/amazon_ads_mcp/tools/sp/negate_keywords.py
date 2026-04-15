"""Sponsored Products negative exact keyword creation."""

from __future__ import annotations

from typing import Any

from .common import normalize_term
from .write_common import (
    SP_NEGATIVE_KEYWORD_MEDIA_TYPE,
    build_mutation_response,
    build_result,
    chunked,
    extract_error_message,
    extract_mutation_items,
    get_sp_write_context,
    is_success_result,
    list_negative_keywords,
    normalize_identifier,
    normalize_negative_keyword_requests,
    sp_post,
)


SUCCESS_CODES = {"SUCCESS", "CREATED"}


def _negative_lookup_key(item: dict[str, Any]) -> str:
    return normalize_term(item.get("keywordText"))


async def negate_keywords(
    campaign_id: str,
    keywords: list[str],
    ad_group_id: str | None = None,
) -> dict[str, Any]:
    """Create negative exact Sponsored Products keywords."""
    normalized_campaign_id = normalize_identifier(campaign_id, "campaign_id")
    normalized_ad_group_id = (
        normalize_identifier(ad_group_id, "ad_group_id") if ad_group_id else None
    )
    normalized_keywords = normalize_negative_keyword_requests(keywords)
    _, profile_id, region, client = await get_sp_write_context()

    existing_items = await list_negative_keywords(
        client,
        campaign_id=normalized_campaign_id,
        ad_group_id=normalized_ad_group_id,
    )
    existing_index = {
        normalize_term(item.get("keywordText")): item
        for item in existing_items
        if str(item.get("matchType") or "").upper() == "NEGATIVE_EXACT"
        and item.get("keywordText")
    }

    results = []
    actionable = []
    for item in normalized_keywords:
        existing = existing_index.get(item["lookup_key"])
        if existing is not None:
            results.append(
                build_result(
                    "skipped",
                    "ALREADY_NEGATED",
                    keyword_text=item["keyword_text"],
                    existing_negative_keyword_id=str(
                        existing.get("keywordId")
                        or existing.get("negativeKeywordId")
                        or ""
                    )
                    or None,
                )
            )
            continue
        actionable.append(item)

    for batch in chunked(actionable):
        negative_keywords = []
        for item in batch:
            payload_item = {
                "campaignId": normalized_campaign_id,
                "keywordText": item["keyword_text"],
                "matchType": "NEGATIVE_EXACT",
                "state": "ENABLED",
            }
            if normalized_ad_group_id:
                payload_item["adGroupId"] = normalized_ad_group_id
            negative_keywords.append(payload_item)

        response = await sp_post(
            client,
            "/sp/negativeKeywords",
            {"negativeKeywords": negative_keywords},
            SP_NEGATIVE_KEYWORD_MEDIA_TYPE,
        )
        response.raise_for_status()
        payload = response.json()
        api_items = extract_mutation_items(payload, "negativeKeywords")
        api_index = {_negative_lookup_key(item): item for item in api_items}

        for item in batch:
            api_result = api_index.get(item["lookup_key"])
            if api_result is None and api_items:
                results.append(
                    build_result(
                        "failed",
                        "MISSING_RESULT",
                        keyword_text=item["keyword_text"],
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
                        negative_keyword_id=str(
                            (api_result or {}).get("keywordId")
                            or (api_result or {}).get("negativeKeywordId")
                            or ""
                        )
                        or None,
                    )
                )
                continue

            results.append(
                build_result(
                    "failed",
                    (api_result.get("code") or api_result.get("status") or "ERROR"),
                    keyword_text=item["keyword_text"],
                    error=extract_error_message(api_result)
                    or "Negative keyword create request was rejected",
                )
            )

    results.sort(key=lambda item: normalize_term(item.get("keyword_text")))
    return build_mutation_response(
        profile_id,
        region,
        results,
        campaign_id=normalized_campaign_id,
        ad_group_id=normalized_ad_group_id,
    )
