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
async def test_build_runs_sp_setup_before_stripping_schemas(monkeypatch):
    fake_auth_manager = SimpleNamespace(provider=None)

    monkeypatch.setattr(
        "amazon_ads_mcp.server.server_builder.get_auth_manager",
        lambda: fake_auth_manager,
    )

    builder = ServerBuilder()
    calls = []

    async def record_default_identity():
        calls.append("default_identity")

    async def record_create_server():
        calls.append("create_server")
        return SimpleNamespace()

    async def record_middleware():
        calls.append("middleware")

    async def record_http_client():
        calls.append("http_client")
        return SimpleNamespace()

    async def record_builtin_tools():
        calls.append("builtin_tools")

    async def record_sp_tools():
        calls.append("sp_tools")

    async def record_strip_schemas():
        calls.append("strip_output_schemas")

    async def record_prompts():
        calls.append("builtin_prompts")

    async def record_oauth_callback():
        calls.append("oauth_callback")

    async def record_health_check():
        calls.append("health_check")

    monkeypatch.setattr(builder, "_setup_default_identity", record_default_identity)
    monkeypatch.setattr(builder, "_create_main_server", record_create_server)
    monkeypatch.setattr(builder, "_setup_middleware", record_middleware)
    monkeypatch.setattr(builder, "_setup_http_client", record_http_client)
    monkeypatch.setattr(builder, "_setup_builtin_tools", record_builtin_tools)
    monkeypatch.setattr(builder, "_setup_sp_tools", record_sp_tools)
    monkeypatch.setattr(builder, "_strip_output_schemas", record_strip_schemas)
    monkeypatch.setattr(builder, "_setup_builtin_prompts", record_prompts)
    monkeypatch.setattr(builder, "_setup_oauth_callback", record_oauth_callback)
    monkeypatch.setattr(builder, "_setup_health_check", record_health_check)

    await builder.build()

    assert calls == [
        "default_identity",
        "create_server",
        "middleware",
        "http_client",
        "builtin_tools",
        "sp_tools",
        "strip_output_schemas",
        "builtin_prompts",
        "oauth_callback",
        "health_check",
    ]


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
