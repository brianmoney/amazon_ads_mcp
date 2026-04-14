from types import SimpleNamespace

import pytest

from amazon_ads_mcp.server.server_builder import ServerBuilder
from amazon_ads_mcp.tools.sp import register_all_sp_tools
from fastmcp import FastMCP


@pytest.mark.asyncio
async def test_register_all_sp_tools_exposes_read_tool_names():
    server = FastMCP("test")

    await register_all_sp_tools(server)

    tool_names = {tool.name for tool in await server.list_tools()}
    assert {
        "list_campaigns",
        "get_keyword_performance",
        "get_search_term_report",
    }.issubset(tool_names)


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
async def test_server_builder_includes_sp_read_tools(builder):
    server = await builder.build()

    tool_names = {tool.name for tool in await server.list_tools()}
    assert "list_campaigns" in tool_names
    assert "get_keyword_performance" in tool_names
    assert "get_search_term_report" in tool_names
