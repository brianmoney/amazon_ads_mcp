from types import SimpleNamespace

import pytest
from fastmcp import FastMCP

from amazon_ads_mcp.server.server_builder import ServerBuilder
from amazon_ads_mcp.tools.portfolio import register_all_portfolio_tools


def _assert_contains(text: str, *parts: str) -> None:
    for part in parts:
        assert part in text


@pytest.mark.asyncio
async def test_register_all_portfolio_tools_exposes_tool_names():
    server = FastMCP("test")

    await register_all_portfolio_tools(server)

    tool_names = {tool.name for tool in await server.list_tools()}
    assert {
        "list_portfolios",
        "get_portfolio_budget_usage",
        "warehouse_get_portfolio_budget_usage",
        "update_portfolio_budget",
    }.issubset(tool_names)


@pytest.mark.asyncio
async def test_register_all_portfolio_tools_publishes_optional_budget_period_inputs():
    server = FastMCP("test")

    await register_all_portfolio_tools(server)

    tool = await server.get_tool("update_portfolio_budget")

    assert tool.parameters["properties"]["start_date"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
        "description": "Required YYYY-MM-DD start date when budget_scope is monthly.",
    }
    assert tool.parameters["properties"]["end_date"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
        "description": "Required YYYY-MM-DD end date when budget_scope is monthly.",
    }
    _assert_contains(
        tool.description,
        "budget_scope=daily",
        "monthly with both start_date and end_date",
    )
    _assert_contains(
        tool.parameters["properties"]["budget_scope"]["description"],
        "daily or monthly",
        "monthly requires both start_date and end_date",
    )


@pytest.mark.asyncio
async def test_register_all_portfolio_tools_publishes_state_filter_guidance():
    server = FastMCP("test")

    await register_all_portfolio_tools(server)

    tool = await server.get_tool("list_portfolios")

    _assert_contains(
        tool.description,
        "normalized to uppercase",
        "unfiltered by state",
    )
    _assert_contains(
        tool.parameters["properties"]["portfolio_states"]["description"],
        "normalized to uppercase",
    )


@pytest.mark.asyncio
async def test_register_all_portfolio_tools_publishes_warehouse_controls():
    server = FastMCP("test")

    await register_all_portfolio_tools(server)

    tool = await server.get_tool("warehouse_get_portfolio_budget_usage")

    _assert_contains(
        tool.description,
        "data_source",
        "freshness",
        "fallback_reason",
    )
    _assert_contains(
        tool.parameters["properties"]["read_preference"]["description"],
        "prefer_warehouse",
        "warehouse_only",
        "live_only",
    )
    _assert_contains(
        tool.parameters["properties"]["max_staleness_minutes"]["description"],
        "maximum allowed warehouse age in minutes",
    )


@pytest.fixture
def builder(monkeypatch):
    fake_auth_manager = SimpleNamespace(provider=None)
    monkeypatch.setattr(
        "amazon_ads_mcp.server.server_builder.get_auth_manager",
        lambda: fake_auth_manager,
    )
    monkeypatch.setattr(
        "amazon_ads_mcp.server.builtin_tools.get_auth_manager",
        lambda: fake_auth_manager,
    )
    monkeypatch.setattr(
        "amazon_ads_mcp.server.builtin_prompts.get_auth_manager",
        lambda: fake_auth_manager,
    )
    return ServerBuilder()


@pytest.mark.asyncio
async def test_server_builder_includes_portfolio_tools(builder):
    server = await builder.build()

    tool_names = {tool.name for tool in await server.list_tools()}
    assert "list_portfolios" in tool_names
    assert "get_portfolio_budget_usage" in tool_names
    assert "warehouse_get_portfolio_budget_usage" in tool_names
    assert "update_portfolio_budget" in tool_names


@pytest.mark.asyncio
async def test_server_builder_publishes_portfolio_metadata(builder):
    server = await builder.build()

    tool = await server.get_tool("update_portfolio_budget")

    _assert_contains(
        tool.description,
        "budget_scope=daily",
        "monthly with both start_date and end_date",
    )
    _assert_contains(
        tool.parameters["properties"]["budget_scope"]["description"],
        "daily or monthly",
        "monthly requires both start_date and end_date",
    )


@pytest.mark.asyncio
async def test_server_builder_publishes_warehouse_portfolio_metadata(builder):
    server = await builder.build()

    tool = await server.get_tool("warehouse_get_portfolio_budget_usage")

    _assert_contains(
        tool.parameters["properties"]["read_preference"]["description"],
        "prefer_warehouse",
        "warehouse_only",
        "live_only",
    )
    _assert_contains(
        tool.parameters["properties"]["max_staleness_minutes"]["description"],
        "maximum allowed warehouse age in minutes",
    )
