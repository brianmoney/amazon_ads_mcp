from types import SimpleNamespace

import pytest
from fastmcp import FastMCP

from amazon_ads_mcp.server.builtin_prompts import register_all_builtin_prompts


@pytest.mark.asyncio
async def test_direct_auth_registers_oauth_setup_prompt(monkeypatch):
    monkeypatch.setattr(
        "amazon_ads_mcp.server.builtin_prompts.get_auth_manager",
        lambda: SimpleNamespace(provider=SimpleNamespace(provider_type="direct")),
    )
    server = FastMCP("test")

    await register_all_builtin_prompts(server)

    prompts = await server.list_prompts()
    prompt_names = {prompt.name for prompt in prompts}

    assert "auth_profile_setup" in prompt_names
    assert "troubleshoot_auth_or_routing" in prompt_names
    assert "setup_region" in prompt_names
    assert "sp_bid_optimization" in prompt_names
    assert "sp_search_term_harvesting" in prompt_names


@pytest.mark.asyncio
async def test_openbridge_auth_skips_oauth_setup_prompt(monkeypatch):
    monkeypatch.setattr(
        "amazon_ads_mcp.server.builtin_prompts.get_auth_manager",
        lambda: SimpleNamespace(provider=SimpleNamespace(provider_type="openbridge")),
    )
    server = FastMCP("test")

    await register_all_builtin_prompts(server)

    prompts = await server.list_prompts()
    prompt_names = {prompt.name for prompt in prompts}

    assert "auth_profile_setup" not in prompt_names
    assert "troubleshoot_auth_or_routing" in prompt_names
    assert "setup_region" in prompt_names
    assert "sp_bid_optimization" in prompt_names
    assert "sp_search_term_harvesting" in prompt_names


@pytest.mark.asyncio
async def test_openbridge_troubleshoot_prompt_only_references_openbridge_tools(
    monkeypatch,
):
    monkeypatch.setattr(
        "amazon_ads_mcp.server.builtin_prompts.get_auth_manager",
        lambda: SimpleNamespace(provider=SimpleNamespace(provider_type="openbridge")),
    )
    server = FastMCP("test")

    await register_all_builtin_prompts(server)

    rendered = await server.render_prompt("troubleshoot_auth_or_routing")
    prompt_text = rendered.messages[0].content.text

    assert "get_active_identity" in prompt_text
    assert "list_identities" in prompt_text
    assert "check_oauth_status" not in prompt_text


@pytest.mark.asyncio
async def test_bid_optimization_prompt_references_supported_sp_tools(monkeypatch):
    monkeypatch.setattr(
        "amazon_ads_mcp.server.builtin_prompts.get_auth_manager",
        lambda: SimpleNamespace(provider=SimpleNamespace(provider_type="direct")),
    )
    server = FastMCP("test")

    await register_all_builtin_prompts(server)

    rendered = await server.render_prompt("sp_bid_optimization")
    prompt_text = rendered.messages[0].content.text

    assert "get_routing_state" in prompt_text
    assert "get_active_profile" in prompt_text
    assert "stop clearly" in prompt_text
    assert "list_campaigns" in prompt_text
    assert "get_keyword_performance" in prompt_text
    assert "adjust_keyword_bids" in prompt_text
    assert "bounded" in prompt_text
    assert "left unchanged with reasons" in prompt_text


@pytest.mark.asyncio
async def test_search_term_harvesting_prompt_references_supported_sp_tools(monkeypatch):
    monkeypatch.setattr(
        "amazon_ads_mcp.server.builtin_prompts.get_auth_manager",
        lambda: SimpleNamespace(provider=SimpleNamespace(provider_type="direct")),
    )
    server = FastMCP("test")

    await register_all_builtin_prompts(server)

    rendered = await server.render_prompt("sp_search_term_harvesting")
    prompt_text = rendered.messages[0].content.text

    assert "get_routing_state" in prompt_text
    assert "get_active_profile" in prompt_text
    assert "get_search_term_report" in prompt_text
    assert "add_keywords" in prompt_text
    assert "negate_keywords" in prompt_text
    assert "harvest, negate, or leave unchanged" in prompt_text
    assert "manual and negative targeting context" in prompt_text
    assert "terms left unchanged with reasons" in prompt_text


@pytest.mark.asyncio
async def test_auth_profile_setup_prompt_references_profile_discovery_tools(
    monkeypatch,
):
    monkeypatch.setattr(
        "amazon_ads_mcp.server.builtin_prompts.get_auth_manager",
        lambda: SimpleNamespace(provider=SimpleNamespace(provider_type="direct")),
    )
    server = FastMCP("test")

    await register_all_builtin_prompts(server)

    rendered = await server.render_prompt("auth_profile_setup")
    prompt_text = rendered.messages[0].content.text

    assert "summarize_profiles" in prompt_text
    assert "search_profiles" in prompt_text
    assert "page_profiles" in prompt_text
    assert "set_active_profile" in prompt_text
