"""Portfolio discovery and normalized budget settings."""

from __future__ import annotations

from typing import Any

import httpx

from .common import (
    PortfolioValidationError,
    get_portfolio_client,
    normalize_portfolio_record,
    portfolio_http_error_message,
    query_portfolios,
    require_portfolio_context,
)


async def list_portfolios(
    portfolio_states: list[str] | None = None,
    portfolio_ids: list[str] | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Return portfolios with normalized budget context."""
    auth_manager, profile_id, region = require_portfolio_context()
    client = await get_portfolio_client(auth_manager)

    try:
        page = await query_portfolios(
            client,
            portfolio_ids=portfolio_ids,
            portfolio_states=portfolio_states,
            limit=limit,
            offset=offset,
        )
    except httpx.HTTPError as exc:
        raise PortfolioValidationError(
            "Portfolio lookup request failed: "
            + portfolio_http_error_message(exc, "Portfolio lookup request failed")
        ) from exc

    portfolios = [
        normalize_portfolio_record(portfolio)
        for portfolio in page["portfolios"]
    ]

    return {
        "profile_id": profile_id,
        "region": region,
        "filters": {
            "portfolio_states": page["portfolio_states"],
            "portfolio_ids": page["portfolio_ids"],
            "limit": page["limit"],
            "offset": page["offset"],
        },
        "next_token": page["next_token"],
        "total_results": page["total_results"],
        "portfolios": portfolios,
        "returned_count": len(portfolios),
    }
