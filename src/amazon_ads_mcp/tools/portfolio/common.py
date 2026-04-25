"""Shared helpers for portfolio tools."""

from __future__ import annotations

from datetime import date
from typing import Any

from ...auth.manager import get_auth_manager
from ...config.settings import Settings
from ...utils.http import get_http_client
from ..sp.common import (
    clamp_limit,
    clamp_offset,
    extract_items,
    normalize_id_list,
    parse_number,
)

MAX_PORTFOLIO_ITEMS = 100
MIN_PORTFOLIO_BUDGET = 0.01
PORTFOLIO_MEDIA_TYPE = "application/vnd.spPortfolio.v3+json"
PORTFOLIO_BUDGET_USAGE_MEDIA_TYPE = (
    "application/vnd.portfoliobudgetusage.v1+json"
)
_MONTHLY_POLICIES = {"DATE_RANGE", "MONTHLY"}


class PortfolioContextError(RuntimeError):
    """Raised when portfolio tools are missing required execution context."""


class PortfolioValidationError(ValueError):
    """Raised when a portfolio tool request is invalid."""


def require_portfolio_context() -> tuple[Any, str, str]:
    """Return the active auth manager, profile, and region for portfolio tools."""
    auth_manager = get_auth_manager()
    profile_id = auth_manager.get_active_profile_id()
    region = auth_manager.get_active_region()

    if not profile_id:
        raise PortfolioContextError(
            "Portfolio tools require an active profile. Use set_active_profile first."
        )

    if not region:
        raise PortfolioContextError(
            "Portfolio tools require an active region. Use set_region first."
        )

    return auth_manager, str(profile_id), str(region)


async def get_portfolio_client(auth_manager=None):
    """Create an authenticated client for portfolio requests."""
    auth_manager = auth_manager or get_auth_manager()
    credentials = await auth_manager.get_active_credentials()
    base_url = credentials.base_url or Settings().region_endpoint
    return await get_http_client(
        authenticated=True,
        auth_manager=auth_manager,
        base_url=base_url,
    )


def media_headers(
    media_type: str,
    *,
    prefer: str | None = None,
) -> dict[str, str]:
    """Return explicit headers for portfolio requests."""
    headers = {"Content-Type": media_type, "Accept": media_type}
    if prefer:
        headers["Prefer"] = prefer
    return headers


async def portfolio_post(
    client: Any,
    path: str,
    payload: dict[str, Any],
    media_type: str,
) -> Any:
    """Send a portfolio POST request with explicit media headers."""
    return await client.post(path, json=payload, headers=media_headers(media_type))


async def portfolio_put(
    client: Any,
    path: str,
    payload: dict[str, Any],
    media_type: str,
    *,
    prefer: str | None = None,
) -> Any:
    """Send a portfolio PUT request with explicit media headers."""
    return await client.put(
        path,
        json=payload,
        headers=media_headers(media_type, prefer=prefer),
    )


def normalize_required_portfolio_ids(
    values: Any,
    field_name: str = "portfolio_ids",
) -> list[str]:
    """Return a bounded list of unique portfolio identifiers."""
    if not isinstance(values, list) or not values:
        raise PortfolioValidationError(f"{field_name} must be a non-empty list")

    normalized = normalize_id_list(values)
    if not normalized:
        raise PortfolioValidationError(f"{field_name} must be a non-empty list")
    if len(normalized) > MAX_PORTFOLIO_ITEMS:
        raise PortfolioValidationError(
            f"{field_name} must contain at most {MAX_PORTFOLIO_ITEMS} items"
        )
    if len(set(normalized)) != len(normalized):
        raise PortfolioValidationError(
            f"{field_name} must not contain duplicate portfolio_id values"
        )

    return normalized


def normalize_portfolio_identifier(
    value: Any,
    field_name: str = "portfolio_id",
) -> str:
    """Return a required single portfolio identifier."""
    identifier = str(value or "").strip()
    if not identifier:
        raise PortfolioValidationError(f"{field_name} is required")
    return identifier


def normalize_portfolio_states(values: list[str] | None) -> list[str]:
    """Return a normalized portfolio state filter."""
    return [
        state.strip().upper() for state in values or [] if str(state).strip()
    ]


def normalize_budget_scope(value: Any) -> str:
    """Return a normalized portfolio budget scope."""
    text = str(value or "").strip().upper()
    if text == "DAILY":
        return "daily"
    if text in {"MONTHLY", "DATE_RANGE"}:
        return "monthly"
    raise PortfolioValidationError(
        "budget_scope must be one of: daily, monthly"
    )


def normalize_budget_amount(
    value: Any,
    field_name: str = "budget_amount",
) -> float:
    """Return a validated portfolio budget amount."""
    amount = parse_number(value)
    if amount is None:
        raise PortfolioValidationError(f"{field_name} must be a number")
    if amount < MIN_PORTFOLIO_BUDGET:
        raise PortfolioValidationError(
            f"{field_name} must be at least {MIN_PORTFOLIO_BUDGET:.2f}"
        )
    return amount


def normalize_optional_iso_date(
    value: Any,
    field_name: str,
) -> str | None:
    """Return an ISO date string when the value is present."""
    if value in (None, ""):
        return None

    text = str(value).strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise PortfolioValidationError(
            f"{field_name} must use YYYY-MM-DD format"
        ) from exc


def normalize_budget_period(
    *,
    budget_scope: str,
    start_date: Any,
    end_date: Any,
) -> tuple[str | None, str | None]:
    """Normalize the supported date fields for a portfolio budget update."""
    normalized_start_date = normalize_optional_iso_date(start_date, "start_date")
    normalized_end_date = normalize_optional_iso_date(end_date, "end_date")

    if budget_scope == "daily":
        if normalized_start_date or normalized_end_date:
            raise PortfolioValidationError(
                "start_date and end_date are only supported for monthly budgets"
            )
        return None, None

    if not normalized_start_date or not normalized_end_date:
        raise PortfolioValidationError(
            "monthly budgets require both start_date and end_date"
        )
    if normalized_start_date > normalized_end_date:
        raise PortfolioValidationError(
            "start_date must be on or before end_date"
        )

    return normalized_start_date, normalized_end_date


def first_present_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-empty value from the provided keys."""
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_portfolio_policy(value: Any) -> str | None:
    """Return a normalized portfolio budget policy."""
    text = str(value or "").strip().upper()
    return text or None


def normalize_portfolio_scope(policy: str | None) -> str | None:
    """Return the normalized budget scope for a portfolio policy."""
    if policy == "DAILY":
        return "daily"
    if policy in _MONTHLY_POLICIES:
        return "monthly"
    return None


def normalize_boolean(value: Any) -> bool | None:
    """Return a best-effort boolean value."""
    if isinstance(value, bool):
        return value
    return None


def extract_portfolio_budget_context(portfolio: dict[str, Any]) -> dict[str, Any]:
    """Return normalized budget fields from a raw portfolio record."""
    budget = portfolio.get("budget")
    if not isinstance(budget, dict):
        budget = {}

    policy = normalize_portfolio_policy(
        first_present_value(budget, ("policy", "budgetType", "budgetPolicy"))
    )
    amount = parse_number(first_present_value(budget, ("amount", "budget")))

    return {
        "budget_policy": policy,
        "budget_scope": normalize_portfolio_scope(policy),
        "cap_amount": amount,
        "daily_budget": amount if policy == "DAILY" else None,
        "monthly_budget": amount if policy in _MONTHLY_POLICIES else None,
        "currency_code": first_present_value(
            budget,
            ("currencyCode", "budgetUnit"),
        ),
        "budget_start_date": first_present_value(budget, ("startDate",)),
        "budget_end_date": first_present_value(budget, ("endDate",)),
    }


def normalize_portfolio_record(portfolio: dict[str, Any]) -> dict[str, Any]:
    """Return a stable normalized portfolio record."""
    budget_controls = portfolio.get("budgetControls")
    if not isinstance(budget_controls, dict):
        budget_controls = {}
    sharing = budget_controls.get("campaignUnspentBudgetSharing")
    if not isinstance(sharing, dict):
        sharing = {}

    extended_data = portfolio.get("extendedData")
    if not isinstance(extended_data, dict):
        extended_data = {}

    status_reasons = extended_data.get("statusReasons")
    if not isinstance(status_reasons, list):
        status_reasons = []

    return {
        "portfolio_id": str(portfolio.get("portfolioId", "")),
        "name": portfolio.get("name"),
        "state": portfolio.get("state"),
        "in_budget": normalize_boolean(portfolio.get("inBudget")),
        "serving_status": extended_data.get("servingStatus"),
        "status_reasons": status_reasons,
        "campaign_unspent_budget_sharing_state": sharing.get("featureState"),
        **extract_portfolio_budget_context(portfolio),
    }


async def query_portfolios(
    client: Any,
    *,
    portfolio_ids: list[str] | None = None,
    portfolio_states: list[str] | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Return filtered portfolio records using the documented list endpoint."""
    normalized_portfolio_ids = normalize_id_list(portfolio_ids)
    normalized_states = normalize_portfolio_states(portfolio_states)
    bounded_limit = clamp_limit(limit)
    bounded_offset = clamp_offset(offset)
    requested_count = bounded_limit + bounded_offset

    collected: list[dict[str, Any]] = []
    next_token: str | None = None
    seen_tokens: set[str] = set()
    total_results: int | None = None

    while len(collected) < requested_count or not collected:
        payload: dict[str, Any] = {"includeExtendedDataFields": True}
        if normalized_portfolio_ids:
            payload["portfolioIdFilter"] = {"include": normalized_portfolio_ids}
        if normalized_states:
            payload["stateFilter"] = {"include": normalized_states}
        if next_token:
            payload["nextToken"] = next_token

        response = await portfolio_post(
            client,
            "/portfolios/list",
            payload,
            PORTFOLIO_MEDIA_TYPE,
        )
        response.raise_for_status()
        response_payload = response.json()

        if isinstance(response_payload, dict):
            parsed_total = parse_number(response_payload.get("totalResults"))
            if parsed_total is not None:
                total_results = int(parsed_total)
            next_token = first_present_value(response_payload, ("nextToken",))
        else:
            next_token = None

        items = extract_items(response_payload, "portfolios")
        if items:
            collected.extend(items)

        if not next_token or next_token in seen_tokens or not items:
            break
        seen_tokens.add(next_token)

    return {
        "portfolio_ids": normalized_portfolio_ids,
        "portfolio_states": normalized_states,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "next_token": next_token,
        "total_results": total_results,
        "portfolios": collected[bounded_offset : bounded_offset + bounded_limit],
    }


__all__ = [
    "MAX_PORTFOLIO_ITEMS",
    "PORTFOLIO_BUDGET_USAGE_MEDIA_TYPE",
    "PORTFOLIO_MEDIA_TYPE",
    "PortfolioContextError",
    "PortfolioValidationError",
    "extract_portfolio_budget_context",
    "first_present_value",
    "get_portfolio_client",
    "normalize_budget_amount",
    "normalize_budget_period",
    "normalize_budget_scope",
    "normalize_portfolio_identifier",
    "normalize_portfolio_record",
    "normalize_required_portfolio_ids",
    "normalize_portfolio_states",
    "parse_number",
    "portfolio_post",
    "portfolio_put",
    "query_portfolios",
    "require_portfolio_context",
]
