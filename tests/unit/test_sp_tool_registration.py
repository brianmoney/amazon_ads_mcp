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
        "sp_report_status",
        "adjust_keyword_bids",
        "add_keywords",
        "negate_keywords",
        "pause_keywords",
        "update_campaign_budget",
    }.issubset(tool_names)


@pytest.mark.asyncio
async def test_register_all_sp_tools_publishes_keyword_resume_input_and_status_tool():
    server = FastMCP("test")

    await register_all_sp_tools(server)

    keyword_tool = await server.get_tool("get_keyword_performance")
    status_tool = await server.get_tool("sp_report_status")

    assert "resume_from_report_id" in keyword_tool.parameters["properties"]
    assert keyword_tool.parameters["properties"]["resume_from_report_id"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
    }
    assert status_tool is not None
    assert status_tool.parameters == {
        "additionalProperties": False,
        "properties": {"report_id": {"type": "string"}},
        "required": ["report_id"],
        "type": "object",
    }


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
    assert "sp_report_status" in tool_names
    assert "adjust_keyword_bids" in tool_names
    assert "add_keywords" in tool_names
    assert "negate_keywords" in tool_names
    assert "pause_keywords" in tool_names
    assert "update_campaign_budget" in tool_names


@pytest.mark.asyncio
async def test_server_builder_publishes_keyword_resume_input_and_status_tool(builder):
    server = await builder.build()

    keyword_tool = await server.get_tool("get_keyword_performance")
    tool_names = {tool.name for tool in await server.list_tools()}

    assert "resume_from_report_id" in keyword_tool.parameters["properties"]
    assert "sp_report_status" in tool_names
