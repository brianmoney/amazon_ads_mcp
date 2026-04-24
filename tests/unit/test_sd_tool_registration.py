from types import SimpleNamespace

import pytest
from fastmcp import FastMCP

from amazon_ads_mcp.server.server_builder import ServerBuilder
from amazon_ads_mcp.tools.sd import register_all_sd_tools


@pytest.mark.asyncio
async def test_register_all_sd_tools_exposes_tool_names():
    server = FastMCP("test")

    await register_all_sd_tools(server)

    tool_names = {tool.name for tool in await server.list_tools()}
    assert {"list_sd_campaigns", "get_sd_performance", "sd_report_status"}.issubset(
        tool_names
    )


@pytest.mark.asyncio
async def test_register_all_sd_tools_publishes_resume_input():
    server = FastMCP("test")

    await register_all_sd_tools(server)

    tool = await server.get_tool("get_sd_performance")

    assert "resume_from_report_id" in tool.parameters["properties"]
    assert tool.parameters["properties"]["resume_from_report_id"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
    }


@pytest.mark.asyncio
async def test_register_all_sd_tools_publishes_status_input():
    server = FastMCP("test")

    await register_all_sd_tools(server)

    tool = await server.get_tool("sd_report_status")

    assert tool.parameters["properties"]["report_id"] == {"title": "Report Id", "type": "string"}
    assert tool.parameters["required"] == ["report_id"]


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
async def test_server_builder_includes_sd_tools(builder):
    server = await builder.build()

    tool_names = {tool.name for tool in await server.list_tools()}
    assert "list_sd_campaigns" in tool_names
    assert "get_sd_performance" in tool_names
    assert "sd_report_status" in tool_names
