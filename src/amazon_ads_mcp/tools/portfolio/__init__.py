"""Portfolio tool registration hooks."""

from __future__ import annotations

from typing import Optional

from fastmcp import Context, FastMCP

from .budget_usage import get_portfolio_budget_usage
from .list_portfolios import list_portfolios
from .update_portfolio_budget import update_portfolio_budget


async def register_all_portfolio_tools(server: FastMCP) -> None:
    """Register the current portfolio tool surface."""

    @server.tool(
        name="list_portfolios",
        description="List portfolios with normalized budget settings",
    )
    async def list_portfolios_tool(
        ctx: Context,
        portfolio_states: Optional[list[str]] = None,
        portfolio_ids: Optional[list[str]] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        return await list_portfolios(
            portfolio_states=portfolio_states,
            portfolio_ids=portfolio_ids,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        name="get_portfolio_budget_usage",
        description=(
            "Get portfolio spend-versus-cap usage with explicit availability "
            "diagnostics"
        ),
    )
    async def get_portfolio_budget_usage_tool(
        ctx: Context,
        portfolio_ids: list[str],
    ) -> dict:
        return await get_portfolio_budget_usage(portfolio_ids=portfolio_ids)

    @server.tool(
        name="update_portfolio_budget",
        description="Update a portfolio daily or monthly budget with audit details",
    )
    async def update_portfolio_budget_tool(
        ctx: Context,
        portfolio_id: str,
        budget_scope: str,
        budget_amount: float,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        return await update_portfolio_budget(
            portfolio_id=portfolio_id,
            budget_scope=budget_scope,
            budget_amount=budget_amount,
            start_date=start_date,
            end_date=end_date,
        )
