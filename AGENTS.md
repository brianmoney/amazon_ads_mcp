# Amazon Ads MCP Development Guidelines

> **Audience**: LLM-driven engineering agents and human developers

Amazon Ads MCP is currently a utility-only MCP server focused on authentication, profile management, region routing, OAuth, sampling, and HTTP client behavior. The generated OpenAPI tool catalog and related bootstrap machinery have been removed.

## Do This First

- Ensure Python >=3.10 and `uv` are installed
- Run `uv sync`
- Start the server with `docker-compose up -d`
- Connect Claude to the MCP server over HTTP:
  - `claude mcp add amazon-ads-mcp -- python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080`
- Verify with `claude mcp list`

## Required Validation

Run these commands in order before committing:

```bash
uv run ruff check --fix
uv run pytest
docker build -t amazon-ads-mcp .
```

All must pass.

## Current Runtime Surface

The retained server surface includes:

- Auth providers and token management
- OAuth callback flow and OAuth tools
- Profile selection and bounded profile listing tools
- Region selection and routing inspection tools
- Sampling middleware and sampling test tool
- HTTP client, middleware, and startup plumbing

The removed surface includes:

- OpenAPI resource mounting
- Generated API tools
- `dist/openapi/resources/`
- OpenAPI sidecars and transforms
- Download tools and file download routes
- Code mode and progressive disclosure

## Editing Guidance

- Keep changes focused and minimal
- Preserve retained auth, profile, region, OAuth, and HTTP client behavior
- Do not reintroduce OpenAPI bootstrap, download routes, or code-mode support unless the task explicitly requires it
- Update tests and docs in the same change when the server surface changes

## Repository Areas

| Path | Purpose |
| --- | --- |
| `src/amazon_ads_mcp/server/` | MCP server bootstrap and built-in utility tools |
| `src/amazon_ads_mcp/auth/` | Authentication providers and token handling |
| `src/amazon_ads_mcp/tools/` | Retained utility tools |
| `src/amazon_ads_mcp/models/` | Pydantic models for retained utility/auth flows |
| `src/amazon_ads_mcp/middleware/` | Authentication, OAuth, caching, and sampling middleware |
| `src/amazon_ads_mcp/utils/` | HTTP client, routing, security, and support utilities |
| `tests/` | Pytest suite |

## Common Commands

```bash
uv sync
uv run ruff check --fix
uv run pytest
docker-compose up -d
docker build -t amazon-ads-mcp .
uv run python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
```

## Guardrails

- Do not push directly to `main`
- Do not log secrets or tokens
- Do not widen scope into unrelated refactors
- Do not restore deleted OpenAPI/download/code-mode machinery as compatibility shims
