# Amazon Ads MCP

Amazon Ads MCP is a Python MCP server for Amazon Ads authentication, profile selection, region routing, OAuth, and HTTP client plumbing.

This repository is currently in a stripped utility-only state. The generated OpenAPI tool catalog, download workflow, code mode, and progressive disclosure machinery have been removed.

## Current Server Surface

The runnable server currently exposes utility tools only:

- `set_active_profile`
- `get_active_profile`
- `clear_active_profile`
- `select_profile`
- `summarize_profiles`
- `search_profiles`
- `page_profiles`
- `refresh_profiles_cache`
- `set_region`
- `get_region`
- `list_regions`
- `get_routing_state`
- OAuth tools when direct auth is configured
- Identity tools when OpenBridge auth is configured
- Sampling test tooling when sampling is enabled

## What Was Removed

- OpenAPI-generated API tools and resource mounting
- `dist/openapi/resources/`
- OpenAPI helper modules and sidecar transforms
- Download tools and HTTP download routes
- Code mode and progressive disclosure support
- Obsolete AMC, DSP, Stores, and generated API response model modules

## Quick Start

```bash
uv sync
docker-compose up -d
uv run python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
```

Connect a client:

```bash
claude mcp add amazon-ads-mcp -- python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
claude mcp list
```

## Authentication

Two auth modes remain supported:

- Direct Amazon Ads OAuth
- OpenBridge identities

Example direct-auth environment:

```bash
export AUTH_METHOD=direct
export AMAZON_AD_API_CLIENT_ID="your-client-id"
export AMAZON_AD_API_CLIENT_SECRET="your-client-secret"
export AMAZON_AD_API_REFRESH_TOKEN="your-refresh-token"
```

Example OpenBridge environment:

```bash
export AUTH_METHOD=openbridge
export OPENBRIDGE_API_KEY="your-api-key"
```

## Development

Required validation flow before committing:

```bash
uv run ruff check --fix
uv run pytest
docker build -t amazon-ads-mcp .
```

## Status

This stripped state is an intermediate server shape that preserves auth, profile, region, OAuth, sampling, and HTTP client behavior while purpose-built SP tools are implemented next.
