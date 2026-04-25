"""Portfolio budget updates with audit-friendly outcomes."""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..sp.write_common import build_mutation_response, build_result
from .common import (
    PORTFOLIO_MEDIA_TYPE,
    get_portfolio_client,
    normalize_budget_amount,
    normalize_budget_period,
    normalize_budget_scope,
    normalize_portfolio_identifier,
    normalize_portfolio_record,
    portfolio_put,
    query_portfolios,
    require_portfolio_context,
)


def _status_from_value(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text or None


def _extract_nested_message(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        for item in value:
            message = _extract_nested_message(item)
            if message:
                return message
        return None
    if not isinstance(value, dict):
        return None

    for key in (
        "message",
        "details",
        "description",
        "detail",
        "error",
        "reason",
    ):
        message = _extract_nested_message(value.get(key))
        if message:
            return message

    for nested_value in value.values():
        if not isinstance(nested_value, (dict, list)):
            continue
        message = _extract_nested_message(nested_value)
        if message:
            return message

    return None


def _extract_update_error_status(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("errorType", "code", "status", "result", "reason"):
            status = _status_from_value(item.get(key))
            if status:
                return status
        errors = item.get("errors")
        if isinstance(errors, list) and errors:
            return _extract_update_error_status(errors[0])
    return "UPDATE_FAILED"


def _extract_update_error_message(item: Any) -> str:
    message = _extract_nested_message(item)
    if message:
        return message
    return "Portfolio budget update request failed"


def _error_message_from_http_error(exc: httpx.HTTPError) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return "Portfolio budget update request failed"

    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        payload = None

    if payload is not None:
        return _extract_update_error_message(payload)

    text = getattr(response, "text", "")
    if isinstance(text, str) and text.strip():
        return text.strip()

    return "Portfolio budget update request failed"


def _extract_update_section(payload: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    container = payload.get("portfolios")
    if isinstance(container, dict):
        value = container.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    value = payload.get(key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _extract_direct_portfolios(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    value = payload.get("portfolios")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _find_update_error_item(payload: Any, portfolio_id: str) -> dict[str, Any] | None:
    error_items = _extract_update_section(payload, "error")
    for item in error_items:
        if str(item.get("portfolioId", "")).strip() == portfolio_id:
            return item
        if item.get("index") == 0:
            return item
    if len(error_items) == 1:
        return error_items[0]
    return None


def _find_updated_portfolio(payload: Any, portfolio_id: str) -> dict[str, Any] | None:
    for item in _extract_update_section(payload, "success"):
        portfolio = item.get("portfolio")
        if not isinstance(portfolio, dict):
            portfolio = item
        candidate_id = str(
            portfolio.get("portfolioId", item.get("portfolioId", ""))
        ).strip()
        if candidate_id == portfolio_id or item.get("index") == 0:
            if "portfolioId" not in portfolio and candidate_id:
                portfolio = {**portfolio, "portfolioId": candidate_id}
            return portfolio

    direct_portfolios = _extract_direct_portfolios(payload)
    for portfolio in direct_portfolios:
        if str(portfolio.get("portfolioId", "")).strip() == portfolio_id:
            return portfolio
    if len(direct_portfolios) == 1:
        return direct_portfolios[0]

    return None


def _build_requested_budget(
    *,
    budget_scope: str,
    budget_amount: float,
    currency_code: str,
    start_date: str | None,
    end_date: str | None,
) -> dict[str, Any]:
    budget = {
        "amount": budget_amount,
        "currencyCode": currency_code,
        "policy": "DAILY" if budget_scope == "daily" else "DATE_RANGE",
    }
    if start_date:
        budget["startDate"] = start_date
    if end_date:
        budget["endDate"] = end_date
    return budget


def _matches_requested_budget(
    current: dict[str, Any],
    *,
    budget_scope: str,
    budget_amount: float,
    start_date: str | None,
    end_date: str | None,
) -> bool:
    if budget_scope == "daily":
        return (
            current.get("budget_policy") == "DAILY"
            and current.get("daily_budget") == budget_amount
        )

    return (
        current.get("budget_scope") == "monthly"
        and current.get("monthly_budget") == budget_amount
        and current.get("budget_start_date") == start_date
        and current.get("budget_end_date") == end_date
    )


def _apply_requested_budget(
    current: dict[str, Any],
    *,
    budget_scope: str,
    budget_amount: float,
    start_date: str | None,
    end_date: str | None,
) -> dict[str, Any]:
    resulting = dict(current)
    resulting["budget_scope"] = budget_scope
    resulting["budget_policy"] = "DAILY" if budget_scope == "daily" else "DATE_RANGE"
    resulting["cap_amount"] = budget_amount
    resulting["daily_budget"] = budget_amount if budget_scope == "daily" else None
    resulting["monthly_budget"] = budget_amount if budget_scope == "monthly" else None
    resulting["budget_start_date"] = start_date if budget_scope == "monthly" else None
    resulting["budget_end_date"] = end_date if budget_scope == "monthly" else None
    return resulting


def _result_budget_fields(prefix: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        f"{prefix}_budget_policy": record.get("budget_policy"),
        f"{prefix}_daily_budget": record.get("daily_budget"),
        f"{prefix}_monthly_budget": record.get("monthly_budget"),
        f"{prefix}_budget_start_date": record.get("budget_start_date"),
        f"{prefix}_budget_end_date": record.get("budget_end_date"),
    }


async def update_portfolio_budget(
    portfolio_id: str,
    budget_scope: str,
    budget_amount: float,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Update a portfolio daily or monthly budget with auditable outcomes."""
    normalized_portfolio_id = normalize_portfolio_identifier(portfolio_id)
    normalized_budget_scope = normalize_budget_scope(budget_scope)
    normalized_budget_amount = normalize_budget_amount(budget_amount)
    normalized_start_date, normalized_end_date = normalize_budget_period(
        budget_scope=normalized_budget_scope,
        start_date=start_date,
        end_date=end_date,
    )

    auth_manager, profile_id, region = require_portfolio_context()
    client = await get_portfolio_client(auth_manager)

    try:
        preflight = await query_portfolios(
            client,
            portfolio_ids=[normalized_portfolio_id],
            limit=1,
            offset=0,
        )
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
                    portfolio_id=normalized_portfolio_id,
                    requested_budget_scope=normalized_budget_scope,
                    requested_budget_amount=normalized_budget_amount,
                    requested_budget_start_date=normalized_start_date,
                    requested_budget_end_date=normalized_end_date,
                    error=_error_message_from_http_error(exc),
                )
            ],
        )

    current_item = preflight["portfolios"][0] if preflight["portfolios"] else None
    if current_item is None:
        return build_mutation_response(
            profile_id,
            region,
            [
                build_result(
                    "failed",
                    "NOT_FOUND",
                    portfolio_id=normalized_portfolio_id,
                    requested_budget_scope=normalized_budget_scope,
                    requested_budget_amount=normalized_budget_amount,
                    requested_budget_start_date=normalized_start_date,
                    requested_budget_end_date=normalized_end_date,
                    error="Portfolio was not found during preflight lookup",
                )
            ],
        )

    current = normalize_portfolio_record(current_item)
    currency_code = str(current.get("currency_code") or "").strip()
    if not currency_code:
        return build_mutation_response(
            profile_id,
            region,
            [
                build_result(
                    "failed",
                    "MISSING_CURRENCY_CODE",
                    portfolio_id=normalized_portfolio_id,
                    requested_budget_scope=normalized_budget_scope,
                    requested_budget_amount=normalized_budget_amount,
                    requested_budget_start_date=normalized_start_date,
                    requested_budget_end_date=normalized_end_date,
                    **_result_budget_fields("previous", current),
                    error=(
                        "Portfolio budget updates require an observed currency code "
                        "from the current portfolio settings."
                    ),
                )
            ],
        )

    if _matches_requested_budget(
        current,
        budget_scope=normalized_budget_scope,
        budget_amount=normalized_budget_amount,
        start_date=normalized_start_date,
        end_date=normalized_end_date,
    ):
        return build_mutation_response(
            profile_id,
            region,
            [
                build_result(
                    "skipped",
                    "ALREADY_SET",
                    portfolio_id=normalized_portfolio_id,
                    requested_budget_scope=normalized_budget_scope,
                    requested_budget_amount=normalized_budget_amount,
                    requested_budget_start_date=normalized_start_date,
                    requested_budget_end_date=normalized_end_date,
                    currency_code=currency_code,
                    **_result_budget_fields("previous", current),
                    **_result_budget_fields("resulting", current),
                )
            ],
        )

    requested_budget = _build_requested_budget(
        budget_scope=normalized_budget_scope,
        budget_amount=normalized_budget_amount,
        currency_code=currency_code,
        start_date=normalized_start_date,
        end_date=normalized_end_date,
    )

    try:
        response = await portfolio_put(
            client,
            "/portfolios",
            {
                "portfolios": [
                    {
                        "portfolioId": normalized_portfolio_id,
                        "budget": requested_budget,
                    }
                ]
            },
            PORTFOLIO_MEDIA_TYPE,
            prefer="return=representation",
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
                    portfolio_id=normalized_portfolio_id,
                    requested_budget_scope=normalized_budget_scope,
                    requested_budget_amount=normalized_budget_amount,
                    requested_budget_start_date=normalized_start_date,
                    requested_budget_end_date=normalized_end_date,
                    currency_code=currency_code,
                    **_result_budget_fields("previous", current),
                    error=_error_message_from_http_error(exc),
                )
            ],
        )

    error_item = _find_update_error_item(payload, normalized_portfolio_id)
    if error_item is not None:
        return build_mutation_response(
            profile_id,
            region,
            [
                build_result(
                    "failed",
                    _extract_update_error_status(error_item),
                    portfolio_id=normalized_portfolio_id,
                    requested_budget_scope=normalized_budget_scope,
                    requested_budget_amount=normalized_budget_amount,
                    requested_budget_start_date=normalized_start_date,
                    requested_budget_end_date=normalized_end_date,
                    currency_code=currency_code,
                    **_result_budget_fields("previous", current),
                    error=_extract_update_error_message(error_item),
                )
            ],
        )

    updated_portfolio = _find_updated_portfolio(payload, normalized_portfolio_id)
    if updated_portfolio is not None:
        resulting = normalize_portfolio_record(updated_portfolio)
    else:
        resulting = _apply_requested_budget(
            current,
            budget_scope=normalized_budget_scope,
            budget_amount=normalized_budget_amount,
            start_date=normalized_start_date,
            end_date=normalized_end_date,
        )

    return build_mutation_response(
        profile_id,
        region,
        [
            build_result(
                "applied",
                "UPDATED",
                portfolio_id=normalized_portfolio_id,
                requested_budget_scope=normalized_budget_scope,
                requested_budget_amount=normalized_budget_amount,
                requested_budget_start_date=normalized_start_date,
                requested_budget_end_date=normalized_end_date,
                currency_code=currency_code,
                **_result_budget_fields("previous", current),
                **_result_budget_fields("resulting", resulting),
            )
        ],
    )
