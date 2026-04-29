"""Warehouse-versus-live validation helpers for the phase 1 ingestion surfaces."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, select

from .live_views import (
    get_campaign_budget_history,
    fetch_live_portfolios,
    get_impression_share_report,
    get_keyword_performance,
    get_placement_report,
    get_portfolio_budget_usage,
    get_search_term_report,
)
from .schema import (
    portfolio,
    portfolio_budget_usage_snapshot,
    sp_campaign_budget_history_fact,
    sp_impression_share_fact,
    sp_keyword_performance_fact,
    sp_placement_fact,
    sp_search_term_fact,
)
from .utils import normalize_date


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return sorted(_normalize_scalar(item) for item in value)
    if isinstance(value, dict):
        return {key: _normalize_scalar(value[key]) for key in sorted(value)}
    return value


def _sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _safe_divide(numerator: Any, denominator: Any) -> float | None:
    if numerator in (None, "") or denominator in (None, ""):
        return None
    try:
        denominator_value = float(denominator)
        if denominator_value == 0:
            return None
        return float(numerator) / denominator_value
    except (TypeError, ValueError):
        return None


def _compare_rows(live_rows: list[dict[str, Any]], warehouse_rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_live = sorted(
        (_normalize_scalar(row) for row in live_rows),
        key=_sort_key,
    )
    normalized_warehouse = sorted(
        (_normalize_scalar(row) for row in warehouse_rows),
        key=_sort_key,
    )
    return {
        "matched": normalized_live == normalized_warehouse,
        "live_count": len(live_rows),
        "warehouse_count": len(warehouse_rows),
        "live_rows": normalized_live,
        "warehouse_rows": normalized_warehouse,
    }


def _mismatch(result: dict[str, Any], surface_name: str) -> dict[str, Any]:
    return {
        "surface_name": surface_name,
        "matched": result["matched"],
        "live_count": result["live_count"],
        "warehouse_count": result["warehouse_count"],
        "details": None if result["matched"] else result,
    }


async def validate_keyword_performance(
    connection: Connection,
    *,
    profile_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Compare warehouse keyword rows with current live tool output."""
    live = await get_keyword_performance(start_date=start_date, end_date=end_date, limit=100)
    warehouse_rows = [
        dict(row._mapping)
        for row in connection.execute(
            select(sp_keyword_performance_fact).where(
                sp_keyword_performance_fact.c.profile_id == profile_id,
                sp_keyword_performance_fact.c.window_start == normalize_date(start_date),
                sp_keyword_performance_fact.c.window_end == normalize_date(end_date),
            )
        )
    ]
    projected_warehouse = [
        {
            "campaign_id": row.get("campaign_id"),
            "ad_group_id": row.get("ad_group_id"),
            "keyword_id": row.get("keyword_id"),
            "keyword_text": row.get("keyword_text"),
            "match_type": row.get("match_type"),
            "bid": row.get("current_bid"),
            "impressions": row.get("impressions"),
            "clicks": row.get("clicks"),
            "spend": row.get("spend"),
            "sales": row.get("sales_14d"),
            "orders": row.get("orders_14d"),
        }
        for row in warehouse_rows
    ]
    return _mismatch(_compare_rows(live["rows"], projected_warehouse), "get_keyword_performance")


async def validate_search_terms(
    connection: Connection,
    *,
    profile_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Compare warehouse search-term facts with live normalized output."""
    live = await get_search_term_report(start_date=start_date, end_date=end_date, limit=100)
    warehouse_rows = [
        dict(row._mapping)
        for row in connection.execute(
            select(sp_search_term_fact).where(
                sp_search_term_fact.c.profile_id == profile_id,
                sp_search_term_fact.c.window_start == normalize_date(start_date),
                sp_search_term_fact.c.window_end == normalize_date(end_date),
            )
        )
    ]
    projected_warehouse = [
        {
            "campaign_id": row.get("campaign_id"),
            "ad_group_id": row.get("ad_group_id"),
            "keyword_id": row.get("keyword_id") or "",
            "keyword_ids": (row.get("targeting_context_json") or {}).get(
                "keyword_ids",
                [row.get("keyword_id")] if row.get("keyword_id") else [],
            ),
            "search_term": row.get("search_term"),
            "match_type": row.get("match_type"),
            "impressions": row.get("impressions"),
            "clicks": row.get("clicks"),
            "spend": row.get("spend"),
            "sales": row.get("sales_14d"),
            "orders": row.get("orders_14d"),
            "manually_targeted": row.get("manually_targeted"),
            "manual_target_ids": (row.get("targeting_context_json") or {}).get(
                "manual_target_ids", []
            ),
            "negated": row.get("negated"),
            "negative_target_ids": (row.get("targeting_context_json") or {}).get(
                "negative_target_ids", []
            ),
            "negative_match_types": (row.get("targeting_context_json") or {}).get(
                "negative_match_types", []
            ),
        }
        for row in warehouse_rows
    ]
    return _mismatch(_compare_rows(live["rows"], projected_warehouse), "get_search_term_report")


async def validate_budget_history(
    connection: Connection,
    *,
    profile_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Compare warehouse budget-history facts with live normalized output."""
    live = await get_campaign_budget_history(
        start_date=start_date,
        end_date=end_date,
        limit=100,
    )
    warehouse_rows = [
        dict(row._mapping)
        for row in connection.execute(
            select(sp_campaign_budget_history_fact).where(
                sp_campaign_budget_history_fact.c.profile_id == profile_id,
                sp_campaign_budget_history_fact.c.budget_date
                >= normalize_date(start_date),
                sp_campaign_budget_history_fact.c.budget_date
                <= normalize_date(end_date),
            )
        )
    ]
    projected_warehouse = [
        {
            "date": row.get("budget_date"),
            "campaign_id": row.get("campaign_id"),
            "campaign_name": row.get("campaign_name"),
            "daily_budget": row.get("daily_budget"),
            "spend": row.get("spend"),
            "utilization_pct": row.get("utilization_pct"),
            "hours_ran": row.get("hours_ran"),
        }
        for row in warehouse_rows
    ]
    return _mismatch(
        _compare_rows(live["rows"], projected_warehouse),
        "get_campaign_budget_history",
    )


async def validate_placement_report(
    connection: Connection,
    *,
    profile_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Compare placement warehouse facts with live normalized output."""
    live = await get_placement_report(
        start_date=start_date,
        end_date=end_date,
        limit=100,
    )
    warehouse_rows = [
        dict(row._mapping)
        for row in connection.execute(
            select(sp_placement_fact).where(
                sp_placement_fact.c.profile_id == profile_id,
                sp_placement_fact.c.window_start == normalize_date(start_date),
                sp_placement_fact.c.window_end == normalize_date(end_date),
            )
        )
    ]
    projected_warehouse = [
        {
            "campaign_id": row.get("campaign_id"),
            "campaign_name": row.get("campaign_name"),
            "placement_type": row.get("placement_type"),
            "impressions": row.get("impressions"),
            "clicks": row.get("clicks"),
            "spend": row.get("spend"),
            "sales14d": row.get("sales_14d"),
            "purchases14d": row.get("purchases_14d"),
            "ctr": _safe_divide(row.get("clicks"), row.get("impressions")),
            "cpc": _safe_divide(row.get("spend"), row.get("clicks")),
            "acos": _safe_divide(row.get("spend"), row.get("sales_14d")),
            "roas": _safe_divide(row.get("sales_14d"), row.get("spend")),
            "current_top_of_search_multiplier": row.get(
                "current_top_of_search_multiplier"
            ),
            "current_product_pages_multiplier": row.get(
                "current_product_pages_multiplier"
            ),
        }
        for row in warehouse_rows
    ]
    return _mismatch(
        _compare_rows(live["rows"], projected_warehouse),
        "get_placement_report",
    )


async def validate_impression_share(
    connection: Connection,
    *,
    profile_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Compare impression-share warehouse rows with live diagnostics."""
    live = await get_impression_share_report(start_date=start_date, end_date=end_date, limit=100)
    warehouse_rows = [
        dict(row._mapping)
        for row in connection.execute(
            select(sp_impression_share_fact).where(
                sp_impression_share_fact.c.profile_id == profile_id,
                sp_impression_share_fact.c.window_start == normalize_date(start_date),
                sp_impression_share_fact.c.window_end == normalize_date(end_date),
            )
        )
    ]
    projected_warehouse = [
        {
            "campaign_id": row.get("campaign_id"),
            "campaign_name": row.get("campaign_name"),
            "top_of_search_impression_share": row.get("top_of_search_impression_share"),
        }
        for row in warehouse_rows
        if row.get("top_of_search_impression_share") is not None
    ]
    row_result = _compare_rows(live.get("rows", []), projected_warehouse)
    availability_matched = _normalize_scalar(live.get("availability") or {}) == _normalize_scalar(
        warehouse_rows[0].get("diagnostic_json") if warehouse_rows else live.get("availability") or {}
    )
    result = _mismatch(row_result, "get_impression_share_report")
    result["availability_matched"] = availability_matched
    if not availability_matched and result["details"] is None:
        result["details"] = {
            "live_availability": live.get("availability") or {},
            "warehouse_availability": warehouse_rows[0].get("diagnostic_json") if warehouse_rows else {},
        }
    result["matched"] = result["matched"] and availability_matched
    return result


async def validate_portfolios(connection: Connection, *, profile_id: str) -> dict[str, Any]:
    """Compare the current portfolio dimension rows with the live list output."""
    live_rows = await fetch_live_portfolios(limit=100)
    warehouse_rows = [
        dict(row._mapping)
        for row in connection.execute(
            select(portfolio).where(portfolio.c.profile_id == profile_id)
        )
    ]
    projected_warehouse = [
        {
            "portfolio_id": row.get("portfolio_id"),
            "name": row.get("name"),
            "state": row.get("state"),
            "in_budget": row.get("in_budget"),
            "serving_status": row.get("serving_status"),
            "status_reasons": row.get("status_reasons_json") or [],
            "campaign_unspent_budget_sharing_state": row.get(
                "campaign_unspent_budget_sharing_state"
            ),
            "budget_policy": row.get("budget_policy"),
            "budget_scope": row.get("budget_scope"),
            "cap_amount": row.get("daily_budget") or row.get("monthly_budget"),
            "daily_budget": row.get("daily_budget"),
            "monthly_budget": row.get("monthly_budget"),
            "currency_code": row.get("currency_code"),
            "budget_start_date": row.get("budget_start_date"),
            "budget_end_date": row.get("budget_end_date"),
        }
        for row in warehouse_rows
    ]
    return _mismatch(_compare_rows(live_rows, projected_warehouse), "list_portfolios")


async def validate_portfolio_usage(
    connection: Connection,
    *,
    profile_id: str,
    portfolio_ids: list[str],
) -> dict[str, Any]:
    """Compare the latest usage snapshots with the live portfolio usage tool."""
    live = await get_portfolio_budget_usage(portfolio_ids)
    warehouse_rows = [
        dict(row._mapping)
        for row in connection.execute(
            select(portfolio_budget_usage_snapshot).where(
                portfolio_budget_usage_snapshot.c.profile_id == profile_id,
                portfolio_budget_usage_snapshot.c.portfolio_id.in_(portfolio_ids),
            )
        )
    ]
    projected_warehouse = [
        {
            "portfolio_id": row.get("portfolio_id"),
            "cap_amount": row.get("cap_amount"),
            "current_spend": row.get("current_spend"),
            "remaining_budget": row.get("remaining_budget"),
            "utilization_pct": row.get("utilization_pct"),
        }
        for row in warehouse_rows
        if row.get("cap_amount") is not None
    ]
    result = _mismatch(
        _compare_rows(live.get("rows", []), projected_warehouse),
        "get_portfolio_budget_usage",
    )
    live_missing = sorted(
        item.get("portfolio_id")
        for item in live.get("diagnostics", [])
        if item.get("portfolio_id")
    )
    warehouse_missing = sorted(
        row.get("portfolio_id")
        for row in warehouse_rows
        if row.get("availability_state") == "unavailable" and row.get("portfolio_id")
    )
    diagnostics_matched = live_missing == warehouse_missing
    result["diagnostics_matched"] = diagnostics_matched
    result["matched"] = result["matched"] and diagnostics_matched
    if not diagnostics_matched and result["details"] is None:
        result["details"] = {
            "live_missing_portfolio_ids": live_missing,
            "warehouse_missing_portfolio_ids": warehouse_missing,
        }
    return result
