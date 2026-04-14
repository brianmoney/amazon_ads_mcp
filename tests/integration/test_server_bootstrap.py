"""Integration tests for Amazon Ads MCP server bootstrap."""

import pytest


@pytest.mark.asyncio
async def test_create_server_bootstrap_without_openapi_resources(monkeypatch):
    from amazon_ads_mcp.auth.manager import AuthManager
    from amazon_ads_mcp.config.settings import Settings
    from amazon_ads_mcp.server.mcp_server import create_amazon_ads_server

    test_settings = Settings(
        _env_file=None,
        auth_method="direct",
        ad_api_client_id="test_client_id",
        ad_api_client_secret="test_client_secret",
        ad_api_refresh_token="test_refresh_token",
    )
    monkeypatch.setattr("amazon_ads_mcp.auth.manager.settings", test_settings)
    AuthManager.reset()

    srv = await create_amazon_ads_server()

    assert srv is not None
