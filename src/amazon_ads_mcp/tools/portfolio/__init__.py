"""Portfolio tool registration hooks."""

from __future__ import annotations

from typing import Annotated, Optional

from fastmcp import Context, FastMCP
from pydantic import Field

from .budget_usage import get_portfolio_budget_usage
from .list_portfolios import list_portfolios
from .update_portfolio_budget import update_portfolio_budget


async def register_all_portfolio_tools(server: FastMCP) -> None:
    """Register the current portfolio tool surface."""

    @server.tool(
        name="list_portfolios",
        description=(
            "List portfolios with normalized budget settings. portfolio_states "
            "is normalized to uppercase when provided, and omitting it leaves "
            "the listing unfiltered by state."
        ),
    )
    async def list_portfolios_tool(
        ctx: Context,
        portfolio_states: Annotated[
            Optional[list[str]],
            Field(
                default=None,
                description="Optional portfolio state filter; values are normalized to uppercase.",
            ),
        ] = None,
        portfolio_ids: Annotated[
            Optional[list[str]],
            Field(default=None, description="Optional list of portfolio IDs to include."),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of portfolios to return in this page."),
        ] = 25,
        offset: Annotated[
            int,
            Field(description="Zero-based page offset for the portfolio listing."),
        ] = 0,
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
            "diagnostics for the requested portfolio_ids."
        ),
    )
    async def get_portfolio_budget_usage_tool(
        ctx: Context,
        portfolio_ids: Annotated[
            list[str],
            Field(description="Required non-empty list of portfolio IDs to inspect."),
        ],
    ) -> dict:
        return await get_portfolio_budget_usage(portfolio_ids=portfolio_ids)

    @server.tool(
        name="update_portfolio_budget",
        description=(
            "Update a portfolio daily or monthly budget with audit details. Use "
            "budget_scope=daily for an always-on cap, or monthly with both "
            "start_date and end_date for a date-range budget."
        ),
    )
    async def update_portfolio_budget_tool(
        ctx: Context,
        portfolio_id: Annotated[
            str,
            Field(description="Required portfolio ID to update."),
        ],
        budget_scope: Annotated[
            str,
            Field(
                description=(
                    "Required budget scope. Supported values: daily or monthly. "
                    "monthly requires both start_date and end_date."
                )
            ),
        ],
        budget_amount: Annotated[
            float,
            Field(description="Required budget amount. Must be at least 0.01."),
        ],
        start_date: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Required YYYY-MM-DD start date when budget_scope is monthly.",
            ),
        ] = None,
        end_date: Annotated[
            Optional[str],
            Field(
                default=None,
                description="Required YYYY-MM-DD end date when budget_scope is monthly.",
            ),
        ] = None,
    ) -> dict:
        return await update_portfolio_budget(
            portfolio_id=portfolio_id,
            budget_scope=budget_scope,
            budget_amount=budget_amount,
            start_date=start_date,
            end_date=end_date,
        )
