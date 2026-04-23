"""Sponsored Display targeting-group performance reporting."""

from __future__ import annotations

from datetime import date
from typing import Any

from ...models.sd_models import (
    SDPerformanceRequest,
    SDPerformanceResponse,
    SDPerformanceRow,
)
from .common import (
    clamp_limit,
    get_sd_client,
    normalize_id_list,
    parse_number,
    require_sd_context,
    safe_divide,
)
from .report_helper import resume_sd_report, run_sd_report

DEFAULT_SD_PERFORMANCE_TIMEOUT_SECONDS = 120.0
SD_REPORT_TYPE_ID = "sdAdGroup"
SD_REPORT_GROUP_BY = ["adGroup"]
SD_PERFORMANCE_REPORT_COLUMNS = [
    "impressions",
    "clicks",
    "cost",
    "campaignId",
    "campaignName",
    "adGroupId",
    "adGroupName",
    "sales",
    "purchases",
    "impressionsViews",
]
_OBJECTIVE_KEYS = ("campaignObjective", "objective")
_BIDDING_MODEL_KEYS = ("biddingModel", "costType")
_TARGETING_GROUP_ID_KEYS = ("targetingGroupId", "adGroupId")
_TARGETING_GROUP_NAME_KEYS = ("targetingGroupName", "adGroupName", "name")
_IMPRESSIONS_KEYS = ("impressions",)
_VIEWABLE_IMPRESSIONS_KEYS = ("viewableImpressions", "impressionsViews")
_SALES_KEYS = ("sales14d", "sales")
_ORDERS_KEYS = ("orders14d", "purchases14d", "purchases", "orders")


def _validate_report_window(start_date: str, end_date: str) -> None:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("Sponsored Display reports require YYYY-MM-DD date inputs.") from exc

    if start > end:
        raise ValueError(
            "Sponsored Display report start_date must be on or before end_date."
        )


def _build_report_filters(objectives: list[str]) -> list[dict[str, Any]]:
    if not objectives:
        return []
    return [{"field": "campaignObjective", "values": objectives}]


def _first_present_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _matches_requested_scope(
    row: dict[str, Any],
    campaign_ids: list[str],
    targeting_group_ids: list[str],
    objectives: list[str],
) -> bool:
    if campaign_ids and str(row.get("campaignId", "")) not in campaign_ids:
        return False

    targeting_group_id = _first_present_value(row, _TARGETING_GROUP_ID_KEYS)
    if targeting_group_ids and str(targeting_group_id or "") not in targeting_group_ids:
        return False

    objective = _first_present_value(row, _OBJECTIVE_KEYS)
    if objectives and str(objective or "").strip().upper() not in objectives:
        return False

    return True


def _is_vcpm_backed(objective: str | None, bidding_model: str | None) -> bool:
    markers = " ".join(part for part in (objective, bidding_model) if part).upper()
    return "VCPM" in markers or "VIEWABLE" in markers or objective == "REACH"


def _safe_thousand_divide(numerator: Any, denominator: Any) -> float | None:
    left = parse_number(numerator)
    right = parse_number(denominator)
    if left is None or right in (None, 0.0):
        return None
    return (left * 1000.0) / right


def _normalize_performance_row(row: dict[str, Any]) -> SDPerformanceRow:
    objective = _first_present_value(row, _OBJECTIVE_KEYS)
    bidding_model = _first_present_value(row, _BIDDING_MODEL_KEYS)
    impressions = parse_number(_first_present_value(row, _IMPRESSIONS_KEYS))
    viewable_impressions = parse_number(
        _first_present_value(row, _VIEWABLE_IMPRESSIONS_KEYS)
    )
    clicks = parse_number(row.get("clicks"))
    spend = parse_number(row.get("cost") or row.get("spend"))
    sales = parse_number(_first_present_value(row, _SALES_KEYS))
    orders = parse_number(_first_present_value(row, _ORDERS_KEYS))
    vcpm_backed = _is_vcpm_backed(
        str(objective) if objective is not None else None,
        str(bidding_model) if bidding_model is not None else None,
    )
    if not vcpm_backed and viewable_impressions not in (None, 0.0):
        vcpm_backed = True
    targeting_group_id = _first_present_value(row, _TARGETING_GROUP_ID_KEYS)

    return SDPerformanceRow(
        campaign_id=str(row.get("campaignId", "")),
        campaign_name=row.get("campaignName"),
        targeting_group_id=(
            str(targeting_group_id) if targeting_group_id is not None else None
        ),
        targeting_group_name=_first_present_value(row, _TARGETING_GROUP_NAME_KEYS),
        objective=str(objective) if objective is not None else None,
        bidding_model=str(bidding_model) if bidding_model is not None else None,
        impressions=impressions,
        viewable_impressions=viewable_impressions,
        clicks=clicks,
        spend=spend,
        sales=sales,
        orders=orders,
        ctr=safe_divide(clicks, impressions),
        cpc=None if vcpm_backed else safe_divide(spend, clicks),
        vcpm=_safe_thousand_divide(spend, viewable_impressions) if vcpm_backed else None,
        acos=safe_divide(spend, sales),
        roas=safe_divide(sales, spend),
    )


async def get_sd_performance(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    targeting_group_ids: list[str] | None = None,
    objectives: list[str] | None = None,
    limit: int = 100,
    resume_from_report_id: str | None = None,
    timeout_seconds: float = DEFAULT_SD_PERFORMANCE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Return normalized Sponsored Display targeting-group performance rows."""
    _validate_report_window(start_date, end_date)

    auth_manager, profile_id, region = require_sd_context()
    client = await get_sd_client(auth_manager)

    request = SDPerformanceRequest(
        start_date=start_date,
        end_date=end_date,
        campaign_ids=normalize_id_list(campaign_ids),
        targeting_group_ids=normalize_id_list(targeting_group_ids),
        objectives=[
            objective.strip().upper()
            for objective in objectives or []
            if str(objective).strip()
        ],
        limit=clamp_limit(limit, default=100),
        resume_from_report_id=resume_from_report_id,
        timeout_seconds=timeout_seconds,
    )

    report_filters = _build_report_filters(request.objectives)

    if request.resume_from_report_id:
        report = await resume_sd_report(request.resume_from_report_id, client=client)
    else:
        report = await run_sd_report(
            report_type_id=SD_REPORT_TYPE_ID,
            start_date=request.start_date,
            end_date=request.end_date,
            group_by=SD_REPORT_GROUP_BY,
            columns=SD_PERFORMANCE_REPORT_COLUMNS,
            filters=report_filters,
            timeout_seconds=request.timeout_seconds,
            client=client,
        )

    filtered_rows = [
        row
        for row in report["rows"]
        if _matches_requested_scope(
            row,
            request.campaign_ids,
            request.targeting_group_ids,
            request.objectives,
        )
    ]
    rows = [
        _normalize_performance_row(row) for row in filtered_rows[: request.limit]
    ]

    response = SDPerformanceResponse(
        profile_id=profile_id,
        region=region,
        start_date=request.start_date,
        end_date=request.end_date,
        report_id=report["report_id"],
        filters=request,
        rows=rows,
        returned_count=len(rows),
    )
    return response.model_dump(mode="json")
