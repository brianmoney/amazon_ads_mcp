"""Portfolio tool registration hooks."""

from __future__ import annotations

from typing import Annotated, Optional

from fastmcp import Context, FastMCP
from pydantic import Field

from .budget_usage import get_portfolio_budget_usage
from .list_portfolios import list_portfolios
from .update_portfolio_budget import update_portfolio_budget


_WAREHOUSE_READ_PREFERENCE_TEXT = (
    "Optional warehouse routing mode. prefer_warehouse checks cached warehouse "
    "data first and falls back to live when needed, warehouse_only refuses live "
    "fallback, and live_only bypasses warehouse lookup while keeping warehouse "
    "provenance metadata in the response."
)
_WAREHOUSE_STALENESS_TEXT = (
    "Optional maximum allowed warehouse age in minutes. When omitted, the "
    "warehouse freshness watermark is reported but not bounded by the caller."
)


async def register_all_portfolio_tools(server: FastMCP) -> None:
    """Register the current portfolio tool surface."""

    from ...warehouse.read_tools import warehouse_get_portfolio_budget_usage

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
        name="warehouse_get_portfolio_budget_usage",
        description=(
            "Read portfolio spend-versus-cap usage from the warehouse when fresh "
            "enough, otherwise fall back to the live tool. The response keeps "
            "the portfolio budget-usage payload shape and adds provenance with "
            "data_source, freshness, and fallback_reason."
        ),
    )
    async def warehouse_get_portfolio_budget_usage_tool(
        ctx: Context,
        portfolio_ids: Annotated[
            list[str],
            Field(description="Required non-empty list of portfolio IDs to inspect."),
        ],
        read_preference: Annotated[
            str,
            Field(description=_WAREHOUSE_READ_PREFERENCE_TEXT),
        ] = "prefer_warehouse",
        max_staleness_minutes: Annotated[
            Optional[int],
            Field(default=None, description=_WAREHOUSE_STALENESS_TEXT),
        ] = None,
    ) -> dict:
        return await warehouse_get_portfolio_budget_usage(
            portfolio_ids=portfolio_ids,
            read_preference=read_preference,
            max_staleness_minutes=max_staleness_minutes,
        )

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
