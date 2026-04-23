"""Sponsored Products campaign budget updates."""

from __future__ import annotations

import json
from typing import Any

import httpx

from .common import parse_number
from .write_common import (
    build_mutation_response,
    build_result,
    get_sp_write_context,
    list_campaigns_for_write,
    normalize_daily_budget,
    normalize_identifier,
    sp_put,
)


def _observed_daily_budget(campaign: dict[str, Any]) -> float | None:
    """Return the current campaign daily budget from common API field variants."""
    return parse_number(campaign.get("dailyBudget")) or parse_number(campaign.get("budget"))


def _error_message_from_http_error(exc: httpx.HTTPError) -> str:
    """Return a readable API rejection message when available."""
    response = getattr(exc, "response", None)
    if response is None:
        return "Campaign budget update request failed"

    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        payload = None

    if isinstance(payload, dict):
        for key in ("message", "detail", "description", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    text = getattr(response, "text", "")
    if isinstance(text, str) and text.strip():
        return text.strip()

    return "Campaign budget update request failed"


async def update_campaign_budget(
    campaign_id: str,
    daily_budget: float,
) -> dict[str, Any]:
    """Update a Sponsored Products campaign daily budget with no-op detection."""
    normalized_campaign_id = normalize_identifier(campaign_id, "campaign_id")
    normalized_daily_budget = normalize_daily_budget(daily_budget)
    _, profile_id, region, client = await get_sp_write_context()

    preflight_items = await list_campaigns_for_write(
        client,
        campaign_ids=[normalized_campaign_id],
    )
    current = next(
        (
            item
            for item in preflight_items
            if str(item.get("campaignId", "")).strip() == normalized_campaign_id
        ),
        None,
    )

    if current is None:
        return build_mutation_response(
            profile_id,
            region,
            [
                build_result(
                    "failed",
                    "NOT_FOUND",
                    campaign_id=normalized_campaign_id,
                    requested_daily_budget=normalized_daily_budget,
                    error="Campaign was not found during preflight lookup",
                )
            ],
        )

    previous_daily_budget = _observed_daily_budget(current)
    if previous_daily_budget == normalized_daily_budget:
        return build_mutation_response(
            profile_id,
            region,
            [
                build_result(
                    "skipped",
                    "ALREADY_SET",
                    campaign_id=normalized_campaign_id,
                    requested_daily_budget=normalized_daily_budget,
                    previous_daily_budget=previous_daily_budget,
                    resulting_daily_budget=previous_daily_budget,
                )
            ],
        )

    try:
        response = await sp_put(
            client,
            f"/sp/campaigns/{normalized_campaign_id}",
            {"dailyBudget": normalized_daily_budget},
            "application/vnd.spCampaign.v3+json",
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        status = f"HTTP_{status_code}" if status_code is not None else "HTTP_ERROR"
        return build_mutation_response(
            profile_id,
            region,
            [
                build_result(
                    "failed",
                    status,
                    campaign_id=normalized_campaign_id,
                    requested_daily_budget=normalized_daily_budget,
                    previous_daily_budget=previous_daily_budget,
                    error=_error_message_from_http_error(exc),
                )
            ],
        )

    resulting_daily_budget = normalized_daily_budget
    if isinstance(payload, dict):
        resulting_daily_budget = (
            _observed_daily_budget(payload) or normalized_daily_budget
        )

    return build_mutation_response(
        profile_id,
        region,
        [
            build_result(
                "applied",
                "UPDATED",
                campaign_id=normalized_campaign_id,
                requested_daily_budget=normalized_daily_budget,
                previous_daily_budget=previous_daily_budget,
                resulting_daily_budget=resulting_daily_budget,
            )
        ],
    )
