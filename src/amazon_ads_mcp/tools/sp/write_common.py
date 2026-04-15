"""Shared helpers for Sponsored Products write tools."""

from __future__ import annotations

from typing import Any, Iterator, Sequence

from .common import (
    extract_items,
    get_sp_client,
    normalize_id_list,
    normalize_term,
    parse_number,
    require_sp_context,
)

MAX_MUTATION_ITEMS = 50
MIN_BID = 0.02
MAX_BID = 100.0
SP_KEYWORD_MEDIA_TYPE = "application/vnd.spKeyword.v3+json"
SP_NEGATIVE_KEYWORD_MEDIA_TYPE = "application/vnd.spNegativeKeyword.v3+json"


class SPWriteValidationError(ValueError):
    """Raised when a Sponsored Products write request is invalid."""


def normalize_bounded_items(items: Any, field_name: str) -> list[Any]:
    """Return a bounded non-empty item list."""
    if not isinstance(items, list) or not items:
        raise SPWriteValidationError(f"{field_name} must be a non-empty list")

    if len(items) > MAX_MUTATION_ITEMS:
        raise SPWriteValidationError(
            f"{field_name} must contain at most {MAX_MUTATION_ITEMS} items"
        )

    return items


def normalize_identifier(value: Any, field_name: str) -> str:
    """Return a required string identifier."""
    identifier = str(value or "").strip()
    if not identifier:
        raise SPWriteValidationError(f"{field_name} is required")
    return identifier


def normalize_keyword_text(value: Any, field_name: str = "keyword_text") -> str:
    """Return a compact keyword phrase."""
    text = " ".join(str(value or "").split())
    if not text:
        raise SPWriteValidationError(f"{field_name} is required")
    return text


def normalize_bid(value: Any, field_name: str = "bid") -> float:
    """Parse and validate a keyword bid."""
    bid = parse_number(value)
    if bid is None:
        raise SPWriteValidationError(f"{field_name} must be a number")
    if bid < MIN_BID or bid > MAX_BID:
        raise SPWriteValidationError(
            f"{field_name} must be between {MIN_BID:.2f} and {MAX_BID:.2f}"
        )
    return bid


def normalize_match_type(
    value: Any,
    default: str = "EXACT",
    allowed: tuple[str, ...] = ("EXACT", "PHRASE", "BROAD"),
) -> str:
    """Normalize a keyword match type."""
    match_type = str(value or default).strip().upper()
    if match_type not in allowed:
        allowed_values = ", ".join(allowed)
        raise SPWriteValidationError(f"match_type must be one of: {allowed_values}")
    return match_type


def normalize_adjustment_requests(adjustments: Any) -> list[dict[str, Any]]:
    """Normalize bid adjustment requests."""
    normalized = []
    for item in normalize_bounded_items(adjustments, "adjustments"):
        if not isinstance(item, dict):
            raise SPWriteValidationError(
                "adjustments must contain objects with keyword_id and new_bid"
            )

        normalized.append(
            {
                "keyword_id": normalize_identifier(
                    item.get("keyword_id"), "keyword_id"
                ),
                "new_bid": normalize_bid(item.get("new_bid"), "new_bid"),
                "reason": str(item.get("reason") or "").strip() or None,
            }
        )
    return normalized


def normalize_keyword_create_requests(keywords: Any) -> list[dict[str, Any]]:
    """Normalize Sponsored Products keyword creation requests."""
    normalized = []
    seen_lookup_keys: set[str] = set()
    for item in normalize_bounded_items(keywords, "keywords"):
        if not isinstance(item, dict):
            raise SPWriteValidationError(
                "keywords must contain objects with keyword_text and bid"
            )

        keyword_text = normalize_keyword_text(item.get("keyword_text"))
        match_type = normalize_match_type(item.get("match_type"), default="EXACT")
        lookup_key = build_lookup_key(
            normalize_term(keyword_text),
            match_type,
        )
        if lookup_key in seen_lookup_keys:
            raise SPWriteValidationError(
                "keywords must not contain duplicate keyword_text/match_type pairs"
            )
        seen_lookup_keys.add(lookup_key)
        normalized.append(
            {
                "keyword_text": keyword_text,
                "match_type": match_type,
                "bid": normalize_bid(item.get("bid"), "bid"),
                "lookup_key": lookup_key,
            }
        )
    return normalized


def normalize_negative_keyword_requests(keywords: Any) -> list[dict[str, Any]]:
    """Normalize negative exact keyword requests."""
    normalized = []
    seen_lookup_keys: set[str] = set()
    for item in normalize_bounded_items(keywords, "keywords"):
        keyword_text = normalize_keyword_text(item, "keyword")
        lookup_key = normalize_term(keyword_text)
        if lookup_key in seen_lookup_keys:
            raise SPWriteValidationError(
                "keywords must not contain duplicate keyword phrases"
            )
        seen_lookup_keys.add(lookup_key)
        normalized.append(
            {
                "keyword_text": keyword_text,
                "match_type": "NEGATIVE_EXACT",
                "lookup_key": lookup_key,
            }
        )
    return normalized


def normalize_keyword_id_requests(
    keyword_ids: Any,
    field_name: str = "keyword_ids",
) -> list[str]:
    """Normalize a bounded list of keyword identifiers."""
    normalized = [
        normalize_identifier(item, "keyword_id")
        for item in normalize_bounded_items(keyword_ids, field_name)
    ]
    normalized = normalize_id_list(normalized)
    if len(set(normalized)) != len(normalized):
        raise SPWriteValidationError(
            f"{field_name} must not contain duplicate keyword_id values"
        )
    return normalized


def build_lookup_key(*parts: Any) -> str:
    """Build a stable case-insensitive lookup key."""
    return "::".join(normalize_term(part) for part in parts if part is not None)


def build_result(outcome: str, status: str, **fields: Any) -> dict[str, Any]:
    """Return a normalized per-item write result."""
    result = {"outcome": outcome, "status": status}
    for key, value in fields.items():
        if value is not None:
            result[key] = value
    return result


def build_mutation_response(
    profile_id: str,
    region: str,
    results: list[dict[str, Any]],
    **fields: Any,
) -> dict[str, Any]:
    """Return a standard write-tool response payload."""
    response = {
        "profile_id": profile_id,
        "region": region,
        "requested_count": len(results),
        "applied_count": sum(1 for item in results if item["outcome"] == "applied"),
        "skipped_count": sum(1 for item in results if item["outcome"] == "skipped"),
        "failed_count": sum(1 for item in results if item["outcome"] == "failed"),
        "results": results,
    }
    response.update(fields)
    return response


def chunked(
    items: Sequence[dict[str, Any]],
    size: int = MAX_MUTATION_ITEMS,
) -> Iterator[list[dict[str, Any]]]:
    """Yield small request batches."""
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def extract_error_message(item: dict[str, Any]) -> str | None:
    """Extract a readable error message from a mutation result row."""
    for key in ("description", "details", "message", "error"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = extract_error_message(value)
            if nested:
                return nested
    return None


def extract_result_code(item: dict[str, Any]) -> str | None:
    """Extract a normalized status or code value."""
    for key in ("code", "status", "result"):
        value = item.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text.upper()
    return None


def is_success_result(
    item: dict[str, Any],
    success_codes: set[str],
) -> bool:
    """Return whether a mutation result row represents success."""
    code = extract_result_code(item)
    if code in success_codes:
        return True
    if extract_error_message(item):
        return False
    if code and any(token in code for token in ("ERROR", "FAIL", "INVALID")):
        return False
    return code is None


def get_item_identifier(
    item: dict[str, Any],
    fields: Sequence[str],
) -> str | None:
    """Return the first matching identifier from an item."""
    for field in fields:
        value = item.get(field)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def index_items_by(
    items: list[dict[str, Any]],
    fields: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Build an identifier index for API result rows."""
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        identifier = get_item_identifier(item, fields)
        if identifier:
            index[identifier] = item
    return index


def extract_mutation_items(payload: Any, primary_key: str) -> list[dict[str, Any]]:
    """Extract common mutation result lists."""
    items = extract_items(payload, primary_key)
    if items:
        return items
    return extract_items(payload, "results")


async def get_sp_write_context() -> tuple[Any, str, str, Any]:
    """Return the active write context and authenticated client."""
    auth_manager, profile_id, region = require_sp_context()
    client = await get_sp_client(auth_manager)
    return auth_manager, profile_id, region, client


def media_headers(media_type: str) -> dict[str, str]:
    """Return explicit media headers for SP write requests."""
    return {"Content-Type": media_type, "Accept": media_type}


def include_filter(values: list[str]) -> dict[str, list[str]]:
    """Wrap identifier filters in the v3 list API include shape."""
    return {"include": normalize_id_list(values)}


async def sp_post(
    client: Any,
    path: str,
    payload: dict[str, Any],
    media_type: str,
) -> Any:
    """Send a POST request with explicit SP media headers."""
    return await client.post(
        path,
        json=payload,
        headers=media_headers(media_type),
    )


async def sp_put(
    client: Any,
    path: str,
    payload: dict[str, Any],
    media_type: str,
) -> Any:
    """Send a PUT request with explicit SP media headers."""
    return await client.put(
        path,
        json=payload,
        headers=media_headers(media_type),
    )


async def list_keywords(
    client: Any,
    *,
    campaign_id: str | None = None,
    ad_group_id: str | None = None,
    keyword_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """List Sponsored Products keywords for preflight checks."""
    payload: dict[str, Any] = {"count": max(len(keyword_ids or []), 100)}
    if campaign_id:
        payload["campaignIdFilter"] = include_filter([campaign_id])
    if ad_group_id:
        payload["adGroupIdFilter"] = include_filter([ad_group_id])
    if keyword_ids:
        payload["keywordIdFilter"] = include_filter(keyword_ids)

    response = await sp_post(
        client, "/sp/keywords/list", payload, SP_KEYWORD_MEDIA_TYPE
    )
    response.raise_for_status()
    return extract_items(response.json(), "keywords")


async def list_negative_keywords(
    client: Any,
    *,
    campaign_id: str,
    ad_group_id: str | None = None,
) -> list[dict[str, Any]]:
    """List Sponsored Products negative keywords for preflight checks."""
    payload: dict[str, Any] = {"campaignIdFilter": [campaign_id], "count": 100}
    if ad_group_id:
        payload["adGroupIdFilter"] = [ad_group_id]

    response = await sp_post(
        client,
        "/sp/negativeKeywords/list",
        payload,
        SP_NEGATIVE_KEYWORD_MEDIA_TYPE,
    )
    response.raise_for_status()
    return extract_items(response.json(), "negativeKeywords")
