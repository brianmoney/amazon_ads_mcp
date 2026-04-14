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
