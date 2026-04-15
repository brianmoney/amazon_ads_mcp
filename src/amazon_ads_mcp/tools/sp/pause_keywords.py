"""Sponsored Products keyword pausing."""

from __future__ import annotations

from typing import Any

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
    normalize_keyword_id_requests,
    sp_put,
)


SUCCESS_CODES = {"SUCCESS", "UPDATED"}


async def pause_keywords(
    keyword_ids: list[str],
    reason: str | None = None,
) -> dict[str, Any]:
    """Pause Sponsored Products keywords while skipping no-op requests."""
    normalized_keyword_ids = normalize_keyword_id_requests(keyword_ids)
    normalized_reason = str(reason or "").strip() or None
    _, profile_id, region, client = await get_sp_write_context()

    preflight_items = await list_keywords(client, keyword_ids=normalized_keyword_ids)
    preflight_index = index_items_by(preflight_items, ("keywordId",))

    results = []
    actionable = []
    for keyword_id in normalized_keyword_ids:
        current = preflight_index.get(keyword_id)
        if current is None:
            results.append(
                build_result(
                    "failed",
                    "NOT_FOUND",
                    keyword_id=keyword_id,
                    reason=normalized_reason,
                    error="Keyword was not found during preflight lookup",
                )
            )
            continue

        current_state = str(current.get("state") or "").upper()
        if current_state == "PAUSED":
            results.append(
                build_result(
                    "skipped",
                    "ALREADY_PAUSED",
                    keyword_id=keyword_id,
                    keyword_text=current.get("keywordText"),
                    previous_state=current.get("state"),
                    resulting_state=current.get("state"),
                    reason=normalized_reason,
                )
            )
            continue

        actionable.append(keyword_id)

    for batch in chunked([{"keyword_id": item} for item in actionable]):
        response = await sp_put(
            client,
            "/sp/keywords",
            {
                "keywords": [
                    {"keywordId": item["keyword_id"], "state": "PAUSED"}
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
            keyword_id = item["keyword_id"]
            current = preflight_index[keyword_id]
            api_result = api_index.get(keyword_id)
            if api_result is None and api_items:
                results.append(
                    build_result(
                        "failed",
                        "MISSING_RESULT",
                        keyword_id=keyword_id,
                        keyword_text=current.get("keywordText"),
                        previous_state=current.get("state"),
                        reason=normalized_reason,
                        error="Mutation response did not include this keyword",
                    )
                )
                continue

            if api_result is None or is_success_result(api_result, SUCCESS_CODES):
                results.append(
                    build_result(
                        "applied",
                        "PAUSED",
                        keyword_id=keyword_id,
                        keyword_text=current.get("keywordText"),
                        previous_state=current.get("state"),
                        resulting_state=(api_result or {}).get("state") or "PAUSED",
                        reason=normalized_reason,
                    )
                )
                continue

            results.append(
                build_result(
                    "failed",
                    get_item_identifier(api_result, ("code", "status")) or "ERROR",
                    keyword_id=keyword_id,
                    keyword_text=current.get("keywordText"),
                    previous_state=current.get("state"),
                    reason=normalized_reason,
                    error=extract_error_message(api_result)
                    or "Keyword pause request was rejected",
                )
            )

    return build_mutation_response(profile_id, region, results)
