from types import SimpleNamespace

import pytest

from amazon_ads_mcp import __version__
from amazon_ads_mcp.server.server_builder import ServerBuilder


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
async def test_build_registers_retained_utility_tools(builder):
    server = await builder.build()

    tools = await server.list_tools()
    tool_names = {tool.name for tool in tools}

    expected = {
        "set_active_profile",
        "get_active_profile",
        "clear_active_profile",
        "select_profile",
        "summarize_profiles",
        "search_profiles",
        "page_profiles",
        "refresh_profiles_cache",
        "set_region",
        "get_region",
        "list_regions",
        "get_routing_state",
    }

    assert expected.issubset(tool_names)
    assert "download_export" not in tool_names
    assert "list_downloads" not in tool_names
    assert "get_download_url" not in tool_names
    assert "list_tool_groups" not in tool_names
    assert "enable_tool_group" not in tool_names


@pytest.mark.asyncio
async def test_build_registers_health_route(builder):
    server = await builder.build()

    assert hasattr(server, "custom_route")


@pytest.mark.asyncio
async def test_health_route_reports_package_version(monkeypatch):
    routes = []
    fake_auth_manager = SimpleNamespace(provider=None)

    monkeypatch.setattr(
        "amazon_ads_mcp.server.server_builder.get_auth_manager",
        lambda: fake_auth_manager,
    )

    class FakeServer:
        def custom_route(self, path, methods=None):
            def decorator(func):
                routes.append((path, methods, func))
                return func

            return decorator

    builder = ServerBuilder()
    builder.server = FakeServer()

    await builder._setup_health_check()

    route = next(route for route in routes if route[0] == "/health")
    response = await route[2](SimpleNamespace())

    assert response.body == (
        f'{{"status":"healthy","service":"amazon-ads-mcp","version":"{__version__}"}}'.encode()
    )
