from types import SimpleNamespace

import pytest

from amazon_ads_mcp.server.server_builder import ServerBuilder
from amazon_ads_mcp.tools.sp import register_all_sp_tools
from fastmcp import FastMCP


def _assert_contains(text: str, *parts: str) -> None:
    for part in parts:
        assert part in text


@pytest.mark.asyncio
async def test_register_all_sp_tools_exposes_read_tool_names():
    server = FastMCP("test")

    await register_all_sp_tools(server)

    tool_names = {tool.name for tool in await server.list_tools()}
    assert {
        "list_campaigns",
        "get_campaign_budget_history",
        "get_impression_share_report",
        "get_keyword_performance",
        "get_placement_report",
        "get_search_term_report",
        "warehouse_get_campaign_budget_history",
        "warehouse_get_impression_share_report",
        "warehouse_get_keyword_performance",
        "warehouse_get_placement_report",
        "warehouse_get_search_term_report",
        "warehouse_get_surface_status",
        "sp_report_status",
        "adjust_keyword_bids",
        "add_keywords",
        "negate_keywords",
        "pause_keywords",
        "update_campaign_budget",
    }.issubset(tool_names)
    assert "warehouse_list_campaigns" not in tool_names
    assert "warehouse_list_portfolios" not in tool_names


@pytest.mark.asyncio
async def test_register_all_sp_tools_publishes_impression_share_resume_input():
    server = FastMCP("test")

    await register_all_sp_tools(server)

    impression_share_tool = await server.get_tool("get_impression_share_report")

    assert "resume_from_report_id" in impression_share_tool.parameters["properties"]
    assert impression_share_tool.parameters["properties"]["resume_from_report_id"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
        "description": (
            "Known report_id to resume instead of creating a new report. Use "
            "the report_id returned by an earlier timeout or in-progress "
            "response."
        ),
    }
    _assert_contains(
        impression_share_tool.parameters["properties"]["timeout_seconds"][
            "description"
        ],
        "Server-side polling timeout for this call only.",
        "resume_from_report_id",
    )


@pytest.mark.asyncio
async def test_register_all_sp_tools_publishes_budget_history_resume_input():
    server = FastMCP("test")

    await register_all_sp_tools(server)

    budget_tool = await server.get_tool("get_campaign_budget_history")

    assert "resume_from_report_id" in budget_tool.parameters["properties"]
    assert budget_tool.parameters["properties"]["resume_from_report_id"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
        "description": (
            "Known report_id to resume instead of creating a new report. Use "
            "the report_id returned by an earlier timeout or in-progress "
            "response."
        ),
    }
    _assert_contains(
        budget_tool.parameters["properties"]["timeout_seconds"]["description"],
        "Server-side polling timeout for this call only.",
        "resume_from_report_id",
    )


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
        "description": (
            "Known report_id to resume instead of creating a new report. Use "
            "the report_id returned by an earlier timeout or in-progress "
            "response."
        ),
    }
    _assert_contains(
        keyword_tool.description,
        "manual keyword rows only",
        "auto-targeting campaigns can legitimately return zero rows",
    )
    _assert_contains(
        keyword_tool.parameters["properties"]["timeout_seconds"]["description"],
        "Server-side polling timeout for this call only.",
        "resume_from_report_id",
    )
    assert status_tool is not None
    assert status_tool.parameters == {
        "additionalProperties": False,
        "properties": {
            "report_id": {
                "description": (
                    "Known Sponsored Products report_id returned by a report tool."
                ),
                "type": "string",
            }
        },
        "required": ["report_id"],
        "type": "object",
    }


@pytest.mark.asyncio
async def test_register_all_sp_tools_publishes_placement_resume_input():
    server = FastMCP("test")

    await register_all_sp_tools(server)

    placement_tool = await server.get_tool("get_placement_report")

    assert "resume_from_report_id" in placement_tool.parameters["properties"]
    assert placement_tool.parameters["properties"]["resume_from_report_id"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
        "description": (
            "Known report_id to resume instead of creating a new report. Use "
            "the report_id returned by an earlier timeout or in-progress "
            "response."
        ),
    }
    _assert_contains(
        placement_tool.parameters["properties"]["timeout_seconds"]["description"],
        "Server-side polling timeout for this call only.",
        "resume_from_report_id",
    )


@pytest.mark.asyncio
async def test_register_all_sp_tools_publishes_warehouse_read_controls():
    server = FastMCP("test")

    await register_all_sp_tools(server)

    keyword_tool = await server.get_tool("warehouse_get_keyword_performance")
    status_tool = await server.get_tool("warehouse_get_surface_status")

    _assert_contains(
        keyword_tool.description,
        "data_source",
        "freshness",
        "fallback_reason",
    )
    _assert_contains(
        keyword_tool.parameters["properties"]["read_preference"]["description"],
        "prefer_warehouse",
        "warehouse_only",
        "live_only",
    )
    _assert_contains(
        keyword_tool.parameters["properties"]["max_staleness_minutes"][
            "description"
        ],
        "maximum allowed warehouse age in minutes",
    )
    _assert_contains(
        status_tool.parameters["properties"]["surface_name"]["description"],
        "get_keyword_performance",
        "get_portfolio_budget_usage",
    )
    _assert_contains(
        status_tool.parameters["properties"]["read_preference"]["description"],
        "prefer_warehouse",
        "warehouse_only",
        "live_only",
    )
    _assert_contains(
        status_tool.parameters["properties"]["max_staleness_minutes"][
            "description"
        ],
        "maximum allowed warehouse age in minutes",
    )


@pytest.mark.asyncio
async def test_register_all_sp_tools_publishes_nested_write_metadata():
    server = FastMCP("test")

    await register_all_sp_tools(server)

    adjust_tool = await server.get_tool("adjust_keyword_bids")
    add_tool = await server.get_tool("add_keywords")

    adjustments = adjust_tool.parameters["properties"]["adjustments"]
    adjustment_items = adjustments["items"]
    keyword_items = add_tool.parameters["properties"]["keywords"]["items"]

    _assert_contains(
        adjust_tool.description,
        "previous_bid or prior_bid",
        "live preflight bid observed at write time",
    )
    assert adjust_tool.parameters["required"] == ["adjustments"]
    _assert_contains(adjustments["description"], "keyword_id, new_bid, reason?")
    assert adjustment_items["required"] == ["keyword_id", "new_bid"]
    _assert_contains(
        adjustment_items["properties"]["new_bid"]["description"],
        "0.02 to 100.00",
    )

    _assert_contains(
        add_tool.description,
        "EXACT, PHRASE, or BROAD",
        "0.02 to 100.00",
    )
    assert add_tool.parameters["required"] == [
        "campaign_id",
        "ad_group_id",
        "keywords",
    ]
    _assert_contains(
        add_tool.parameters["properties"]["campaign_id"]["description"],
        "campaign ID",
    )
    _assert_contains(
        keyword_items["properties"]["match_type"]["description"],
        "EXACT, PHRASE, or BROAD",
        "Defaults to EXACT",
    )
    _assert_contains(
        keyword_items["properties"]["bid"]["description"],
        "0.02 to 100.00",
    )


@pytest.mark.asyncio
async def test_register_all_sp_tools_publishes_campaign_state_guidance():
    server = FastMCP("test")

    await register_all_sp_tools(server)

    tool = await server.get_tool("list_campaigns")

    _assert_contains(
        tool.description,
        "ENABLED, PAUSED, or ARCHIVED",
        "leaves state unfiltered when omitted",
    )
    _assert_contains(
        tool.parameters["properties"]["campaign_states"]["description"],
        "Accepted values: ENABLED, PAUSED, or ARCHIVED.",
        "normalized to uppercase",
        "Omit this filter",
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
async def test_server_builder_includes_sp_read_tools(builder):
    server = await builder.build()

    tool_names = {tool.name for tool in await server.list_tools()}
    assert "list_campaigns" in tool_names
    assert "get_campaign_budget_history" in tool_names
    assert "get_impression_share_report" in tool_names
    assert "get_keyword_performance" in tool_names
    assert "get_placement_report" in tool_names
    assert "get_search_term_report" in tool_names
    assert "warehouse_get_campaign_budget_history" in tool_names
    assert "warehouse_get_impression_share_report" in tool_names
    assert "warehouse_get_keyword_performance" in tool_names
    assert "warehouse_get_placement_report" in tool_names
    assert "warehouse_get_search_term_report" in tool_names
    assert "warehouse_get_surface_status" in tool_names
    assert "warehouse_list_campaigns" not in tool_names
    assert "warehouse_list_portfolios" not in tool_names
    assert "sp_report_status" in tool_names
    assert "adjust_keyword_bids" in tool_names
    assert "add_keywords" in tool_names
    assert "negate_keywords" in tool_names
    assert "pause_keywords" in tool_names
    assert "update_campaign_budget" in tool_names


@pytest.mark.asyncio
async def test_server_builder_publishes_impression_share_resume_input(builder):
    server = await builder.build()

    impression_share_tool = await server.get_tool("get_impression_share_report")

    assert "resume_from_report_id" in impression_share_tool.parameters["properties"]
    _assert_contains(
        impression_share_tool.parameters["properties"]["timeout_seconds"][
            "description"
        ],
        "Server-side polling timeout for this call only.",
        "resume_from_report_id",
    )


@pytest.mark.asyncio
async def test_server_builder_publishes_budget_history_resume_input(builder):
    server = await builder.build()

    budget_tool = await server.get_tool("get_campaign_budget_history")

    assert "resume_from_report_id" in budget_tool.parameters["properties"]
    _assert_contains(
        budget_tool.parameters["properties"]["timeout_seconds"]["description"],
        "Server-side polling timeout for this call only.",
        "resume_from_report_id",
    )


@pytest.mark.asyncio
async def test_server_builder_publishes_keyword_resume_input_and_status_tool(builder):
    server = await builder.build()

    keyword_tool = await server.get_tool("get_keyword_performance")
    tool_names = {tool.name for tool in await server.list_tools()}

    assert "resume_from_report_id" in keyword_tool.parameters["properties"]
    _assert_contains(
        keyword_tool.description,
        "manual keyword rows only",
        "auto-targeting campaigns can legitimately return zero rows",
    )
    assert "sp_report_status" in tool_names


@pytest.mark.asyncio
async def test_server_builder_publishes_placement_resume_input(builder):
    server = await builder.build()

    placement_tool = await server.get_tool("get_placement_report")

    assert "resume_from_report_id" in placement_tool.parameters["properties"]
    _assert_contains(
        placement_tool.parameters["properties"]["timeout_seconds"]["description"],
        "Server-side polling timeout for this call only.",
        "resume_from_report_id",
    )


@pytest.mark.asyncio
async def test_server_builder_publishes_warehouse_tool_metadata(builder):
    server = await builder.build()

    keyword_tool = await server.get_tool("warehouse_get_keyword_performance")
    status_tool = await server.get_tool("warehouse_get_surface_status")

    _assert_contains(
        keyword_tool.parameters["properties"]["read_preference"]["description"],
        "prefer_warehouse",
        "warehouse_only",
        "live_only",
    )
    _assert_contains(
        keyword_tool.parameters["properties"]["max_staleness_minutes"][
            "description"
        ],
        "maximum allowed warehouse age in minutes",
    )
    _assert_contains(
        status_tool.parameters["properties"]["surface_name"]["description"],
        "get_keyword_performance",
        "get_portfolio_budget_usage",
    )
    _assert_contains(
        status_tool.parameters["properties"]["read_preference"]["description"],
        "prefer_warehouse",
        "warehouse_only",
        "live_only",
    )
    _assert_contains(
        status_tool.parameters["properties"]["max_staleness_minutes"][
            "description"
        ],
        "maximum allowed warehouse age in minutes",
    )


@pytest.mark.asyncio
async def test_server_builder_publishes_nested_sp_write_metadata(builder):
    server = await builder.build()

    adjust_tool = await server.get_tool("adjust_keyword_bids")
    add_tool = await server.get_tool("add_keywords")

    adjustment_items = adjust_tool.parameters["properties"]["adjustments"][
        "items"
    ]
    keyword_items = add_tool.parameters["properties"]["keywords"]["items"]

    _assert_contains(
        adjust_tool.description,
        "previous_bid or prior_bid",
        "live preflight bid observed at write time",
    )
    _assert_contains(
        adjustment_items["properties"]["new_bid"]["description"],
        "0.02 to 100.00",
    )
    _assert_contains(
        keyword_items["properties"]["match_type"]["description"],
        "EXACT, PHRASE, or BROAD",
    )


@pytest.mark.asyncio
async def test_server_builder_publishes_campaign_state_metadata(builder):
    server = await builder.build()

    tool = await server.get_tool("list_campaigns")

    _assert_contains(
        tool.parameters["properties"]["campaign_states"]["description"],
        "ENABLED, PAUSED, or ARCHIVED.",
        "normalized to uppercase",
        "Omit this filter",
    )
