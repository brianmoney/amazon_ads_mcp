"""Sponsored Products campaign budget-history reporting."""

from __future__ import annotations

from datetime import date
import logging
from typing import Any

import httpx

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


logger = logging.getLogger(__name__)


DEFAULT_BUDGET_HISTORY_TIMEOUT_SECONDS = 120.0
BUDGET_HISTORY_REPORT_COLUMNS = [
    "campaignId",
    "campaignName",
    "date",
    "cost",
    "campaignBudgetAmount",
]
_DATE_KEYS = ("date", "reportDate", "day")
_CAMPAIGN_NAME_KEYS = ("campaignName", "name")
_BUDGET_KEYS = (
    "dailyBudget",
    "budget",
    "campaignBudget",
    "campaignBudgetAmount",
)
_SPEND_KEYS = ("cost", "spend")
_HOURS_RAN_KEYS = ("hoursRan", "hours_ran", "hoursActive")


def _validate_report_window(start_date: str, end_date: str) -> None:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("Budget history reports require YYYY-MM-DD date inputs.") from exc

    if start > end:
        raise ValueError(
            "Campaign budget history start_date must be on or before end_date."
        )


def _first_present_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _matches_requested_scope(row: dict[str, Any], campaign_ids: list[str]) -> bool:
    if campaign_ids and str(row.get("campaignId", "")) not in campaign_ids:
        return False
    return True


async def _fetch_campaign_name_context(
    client, campaign_ids: list[str]
) -> dict[str, str | None]:
    if not campaign_ids:
        return {}

    response = await sp_post(
        client,
        "/sp/campaigns/list",
        {
            "count": clamp_limit(len(campaign_ids), default=100),
            "campaignIdFilter": {"include": campaign_ids},
        },
        SP_CAMPAIGN_MEDIA_TYPE,
    )
    response.raise_for_status()

    contexts: dict[str, str | None] = {}
    for campaign in extract_items(response.json(), "campaigns"):
        campaign_id = campaign.get("campaignId")
        if campaign_id is None:
            continue
        contexts[str(campaign_id)] = _first_present_value(campaign, _CAMPAIGN_NAME_KEYS)
    return contexts


def _normalize_budget_history_row(
    row: dict[str, Any], campaign_context: dict[str, str | None]
) -> dict[str, Any]:
    campaign_id = str(row.get("campaignId", ""))
    daily_budget = parse_number(_first_present_value(row, _BUDGET_KEYS))
    spend = parse_number(_first_present_value(row, _SPEND_KEYS))
    utilization_ratio = safe_divide(spend, daily_budget)

    return {
        "date": _first_present_value(row, _DATE_KEYS),
        "campaign_id": campaign_id,
        "campaign_name": _first_present_value(row, _CAMPAIGN_NAME_KEYS)
        or campaign_context.get(campaign_id),
        "daily_budget": daily_budget,
        "spend": spend,
        "utilization_pct": (
            utilization_ratio * 100 if utilization_ratio is not None else None
        ),
        "hours_ran": parse_number(_first_present_value(row, _HOURS_RAN_KEYS)),
    }


async def get_campaign_budget_history(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    limit: int = 100,
    resume_from_report_id: str | None = None,
    timeout_seconds: float = DEFAULT_BUDGET_HISTORY_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Return normalized daily campaign budget-history rows for pacing analysis."""
    _validate_report_window(start_date, end_date)

    auth_manager, profile_id, region = require_sp_context()
    client = await get_sp_client(auth_manager)

    normalized_campaign_ids = normalize_id_list(campaign_ids)
    if resume_from_report_id:
        report = await resume_sp_report(resume_from_report_id, client=client)
    else:
        report = await run_sp_report(
            report_type_id="spCampaigns",
            start_date=start_date,
            end_date=end_date,
            group_by=["campaign"],
            columns=BUDGET_HISTORY_REPORT_COLUMNS,
            time_unit="DAILY",
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

    campaign_context: dict[str, str | None] = {}
    missing_campaign_name_ids = sorted(
        {
            str(row.get("campaignId"))
            for row in limited_rows
            if row.get("campaignId") is not None
            and not _first_present_value(row, _CAMPAIGN_NAME_KEYS)
        }
    )
    if missing_campaign_name_ids:
        try:
            campaign_context = await _fetch_campaign_name_context(
                client, missing_campaign_name_ids
            )
        except (httpx.HTTPError, ValueError):
            logger.debug(
                "Budget history campaign lookup failed for campaigns %s; returning rows without campaign context.",
                missing_campaign_name_ids,
                exc_info=True,
            )
            campaign_context = {}

    rows = [
        _normalize_budget_history_row(row, campaign_context)
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
