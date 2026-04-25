"""Portfolio spend-versus-cap usage."""

from __future__ import annotations

from typing import Any

from .common import (
    PORTFOLIO_BUDGET_USAGE_MEDIA_TYPE,
    get_portfolio_client,
    normalize_portfolio_record,
    normalize_required_portfolio_ids,
    parse_number,
    portfolio_post,
    query_portfolios,
    require_portfolio_context,
)


def _extract_usage_items(payload: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    value = payload.get(key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]

    container = payload.get("portfolios")
    if isinstance(container, dict):
        value = container.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return []


def _normalize_row_availability(
    portfolio_id: str,
    *,
    settings: dict[str, Any] | None,
    usage_budget: float | None,
    current_spend: float | None,
    remaining_budget: float | None,
) -> dict[str, Any]:
    missing_fields: list[str] = []
    if settings is None:
        missing_fields.extend(
            [
                "name",
                "state",
                "budget_policy",
                "budget_scope",
                "currency_code",
                "daily_budget",
                "monthly_budget",
                "budget_start_date",
                "budget_end_date",
            ]
        )
    if usage_budget is None:
        missing_fields.append("cap_amount")
    if current_spend is None:
        missing_fields.append("current_spend")
    if remaining_budget is None:
        missing_fields.append("remaining_budget")

    if not missing_fields:
        return {
            "state": "available",
            "reason": None,
            "missing_fields": [],
        }

    if settings is None:
        reason = (
            "Portfolio settings were unavailable for this portfolio, so only "
            "partial budget-usage context could be returned."
        )
    else:
        reason = (
            "Some portfolio budget usage fields were unavailable for this "
            "portfolio."
        )

    return {
        "state": "partial",
        "reason": reason,
        "missing_fields": missing_fields,
    }


def _normalize_usage_row(
    item: dict[str, Any],
    settings: dict[str, Any] | None,
) -> dict[str, Any]:
    portfolio_id = str(item.get("portfolioId", "")).strip()
    usage_budget = parse_number(item.get("budget"))
    usage_pct = parse_number(item.get("budgetUsagePercent"))

    current_spend = None
    remaining_budget = None
    if usage_budget is not None and usage_pct is not None:
        current_spend = usage_budget * (usage_pct / 100.0)
        remaining_budget = usage_budget - current_spend

    base = dict(settings or {})
    if not base:
        base = {
            "portfolio_id": portfolio_id,
            "name": None,
            "state": None,
            "in_budget": None,
            "serving_status": None,
            "status_reasons": [],
            "campaign_unspent_budget_sharing_state": None,
            "budget_policy": None,
            "budget_scope": None,
            "cap_amount": None,
            "daily_budget": None,
            "monthly_budget": None,
            "currency_code": None,
            "budget_start_date": None,
            "budget_end_date": None,
        }

    cap_amount = usage_budget
    if cap_amount is None:
        cap_amount = base.get("cap_amount")

    budget_scope = base.get("budget_scope")
    daily_budget = base.get("daily_budget")
    monthly_budget = base.get("monthly_budget")
    if usage_budget is not None:
        if budget_scope == "daily":
            daily_budget = usage_budget
        elif budget_scope == "monthly":
            monthly_budget = usage_budget

    availability = _normalize_row_availability(
        portfolio_id,
        settings=settings,
        usage_budget=cap_amount,
        current_spend=current_spend,
        remaining_budget=remaining_budget,
    )

    return {
        "portfolio_id": portfolio_id,
        "name": base.get("name"),
        "state": base.get("state"),
        "in_budget": base.get("in_budget"),
        "serving_status": base.get("serving_status"),
        "status_reasons": base.get("status_reasons", []),
        "campaign_unspent_budget_sharing_state": base.get(
            "campaign_unspent_budget_sharing_state"
        ),
        "budget_policy": base.get("budget_policy"),
        "budget_scope": budget_scope,
        "cap_amount": cap_amount,
        "daily_budget": daily_budget,
        "monthly_budget": monthly_budget,
        "currency_code": base.get("currency_code"),
        "budget_start_date": base.get("budget_start_date"),
        "budget_end_date": base.get("budget_end_date"),
        "current_spend": current_spend,
        "remaining_budget": remaining_budget,
        "utilization_pct": usage_pct,
        "usage_updated_timestamp": item.get("usageUpdatedTimestamp"),
        "availability": availability,
    }


def _normalize_usage_diagnostic(
    item: dict[str, Any],
    requested_portfolio_ids: list[str],
) -> dict[str, Any]:
    index_value = item.get("index")
    index = index_value if isinstance(index_value, int) else None
    portfolio_id = str(item.get("portfolioId", "")).strip() or None
    if portfolio_id is None and index is not None and 0 <= index < len(
        requested_portfolio_ids
    ):
        portfolio_id = requested_portfolio_ids[index]

    return {
        "portfolio_id": portfolio_id,
        "state": "unavailable",
        "code": str(item.get("code", "UNKNOWN")).strip() or "UNKNOWN",
        "details": item.get("details"),
        "index": index,
    }


def _build_overall_availability(
    requested_portfolio_ids: list[str],
    rows: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
) -> dict[str, Any]:
    returned_portfolio_ids = {
        row["portfolio_id"] for row in rows if row.get("portfolio_id")
    }
    diagnostic_ids = {
        item["portfolio_id"]
        for item in diagnostics
        if item.get("portfolio_id")
    }
    missing_portfolio_ids = sorted(
        set(requested_portfolio_ids) - returned_portfolio_ids
    )

    if not rows:
        return {
            "state": "unavailable",
            "reason": (
                "Portfolio budget usage data could not be retrieved for the "
                "requested scope."
            ),
            "missing_portfolio_ids": missing_portfolio_ids,
        }

    if diagnostics or missing_portfolio_ids or any(
        row["availability"]["state"] != "available" for row in rows
    ):
        return {
            "state": "partial",
            "reason": (
                "Portfolio budget usage data was only partially available for "
                "the requested scope."
            ),
            "missing_portfolio_ids": sorted(
                set(missing_portfolio_ids) | diagnostic_ids
            ),
        }

    return {
        "state": "available",
        "reason": None,
        "missing_portfolio_ids": [],
    }


async def get_portfolio_budget_usage(portfolio_ids: list[str]) -> dict[str, Any]:
    """Return normalized portfolio spend-versus-cap usage rows."""
    normalized_portfolio_ids = normalize_required_portfolio_ids(portfolio_ids)

    auth_manager, profile_id, region = require_portfolio_context()
    client = await get_portfolio_client(auth_manager)

    settings_page = await query_portfolios(
        client,
        portfolio_ids=normalized_portfolio_ids,
        limit=len(normalized_portfolio_ids),
        offset=0,
    )
    settings_by_portfolio_id = {
        record["portfolio_id"]: record
        for record in (
            normalize_portfolio_record(portfolio)
            for portfolio in settings_page["portfolios"]
        )
        if record.get("portfolio_id")
    }

    usage_response = await portfolio_post(
        client,
        "/portfolios/budget/usage",
        {"portfolioIds": normalized_portfolio_ids},
        PORTFOLIO_BUDGET_USAGE_MEDIA_TYPE,
    )
    usage_response.raise_for_status()
    payload = usage_response.json()

    success_items = _extract_usage_items(payload, "success")
    error_items = _extract_usage_items(payload, "error")

    rows = [
        _normalize_usage_row(
            item,
            settings_by_portfolio_id.get(str(item.get("portfolioId", "")).strip()),
        )
        for item in success_items
        if str(item.get("portfolioId", "")).strip()
    ]
    diagnostics = [
        _normalize_usage_diagnostic(item, normalized_portfolio_ids)
        for item in error_items
    ]

    returned_portfolio_ids = {
        row["portfolio_id"] for row in rows if row.get("portfolio_id")
    }
    diagnosed_portfolio_ids = {
        item["portfolio_id"]
        for item in diagnostics
        if item.get("portfolio_id")
    }
    for portfolio_id in normalized_portfolio_ids:
        if portfolio_id not in returned_portfolio_ids and portfolio_id not in diagnosed_portfolio_ids:
            diagnostics.append(
                {
                    "portfolio_id": portfolio_id,
                    "state": "unavailable",
                    "code": "MISSING_RESULT",
                    "details": (
                        "Portfolio budget usage results did not include this "
                        "portfolio."
                    ),
                    "index": None,
                }
            )

    availability = _build_overall_availability(
        normalized_portfolio_ids,
        rows,
        diagnostics,
    )

    return {
        "profile_id": profile_id,
        "region": region,
        "filters": {"portfolio_ids": normalized_portfolio_ids},
        "availability": availability,
        "diagnostics": diagnostics,
        "rows": rows,
        "returned_count": len(rows),
    }
