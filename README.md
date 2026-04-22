# Amazon Ads MCP

Amazon Ads MCP is a Python MCP server that provides Amazon Ads authentication, profile and region management, and a purpose-built set of Sponsored Products tools for campaign management, keyword analysis, bid optimization, and search term harvesting.

## Server Surface

### Sponsored Products Tools

- `list_campaigns` — List SP campaigns with nested ad groups
- `get_keyword_performance` — Async keyword performance report with derived metrics (ACOS, ROAS, CPC, CTR)
- `get_search_term_report` — Async search term report with manual/negative keyword context
- `sp_report_status` — Check the lifecycle status of an in-progress report by ID
- `adjust_keyword_bids` — Batch bid updates with before/after audit trail
- `add_keywords` — Add SP keywords with duplicate detection
- `negate_keywords` — Add negative exact keywords to a campaign or ad group
- `pause_keywords` — Pause SP keywords with no-op detection

### Profile and Region Management

- `set_active_profile` / `get_active_profile` / `clear_active_profile`
- `select_profile` — Interactive profile selection via MCP elicitation
- `summarize_profiles` / `search_profiles` / `page_profiles` / `refresh_profiles_cache`
- `set_region` / `get_region` / `list_regions` / `get_routing_state`

### Conditional Tools

- OAuth tools (`start_oauth_flow`, `check_oauth_status`, `refresh_oauth_token`, `clear_oauth_tokens`) — direct auth only
- Identity tools (`set_active_identity`, `get_active_identity`, `list_identities`) — OpenBridge only
- `test_sampling` — when `SAMPLING_ENABLED=true`

### Workflow Prompts

- `sp_bid_optimization` — Guided bid optimization workflow
- `sp_search_term_harvesting` — Guided search term harvest and negation workflow
- `auth_profile_setup` — Complete authentication and profile setup (direct auth)
- `troubleshoot_auth_or_routing` / `setup_region`

## Quick Start

```bash
uv sync
docker compose build
docker compose up -d
uv run python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
```

Connect a client:

```bash
claude mcp add amazon-ads-mcp -- python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
claude mcp list
```

## Authentication

Two auth modes are supported:

### Direct Amazon Ads OAuth

Use this when you have your own Amazon Ads API application (BYOA — Bring Your Own App).

The fastest path to a working `AMAZON_AD_API_REFRESH_TOKEN` is the built-in OAuth tool. Set your Client ID and Secret, start the server, then run `start_oauth_flow` — it generates an authorization URL, opens your browser, and stores the resulting tokens automatically.

Required environment:

```bash
AUTH_METHOD=direct
AMAZON_AD_API_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
AMAZON_AD_API_CLIENT_SECRET="your-client-secret"
```

Optional — if you already have a refresh token from a previous OAuth grant:

```bash
AMAZON_AD_API_REFRESH_TOKEN="Atzr|IwEB..."
```

If `AMAZON_AD_API_REFRESH_TOKEN` is not set, run `start_oauth_flow` after the server starts to complete the authorization and store the token.

See [INSTALL.md](INSTALL.md) for full credential setup instructions including how to register an LWA application.

### OpenBridge

Use this when your Amazon Ads accounts are managed through [OpenBridge](https://openbridge.com), a multi-tenant identity broker. Instead of managing Amazon OAuth credentials yourself, OpenBridge holds the per-account credentials and issues tokens on request.

How it works: you provide an OpenBridge refresh token, the server exchanges it for a short-lived JWT, uses that JWT to list your Amazon Ads remote identities, and then fetches per-identity Amazon Ads bearer tokens. Region routing is identity-controlled — it follows the region recorded in each identity's attributes.

Required environment:

```bash
AUTH_METHOD=openbridge
OPENBRIDGE_REFRESH_TOKEN="your-openbridge-refresh-token"
```

`OPENBRIDGE_API_KEY` is accepted as a legacy alias for `OPENBRIDGE_REFRESH_TOKEN`.

The refresh token can also be passed per-request via the `Authorization: Bearer` header (preferred for gateway/proxy deployments) or the `X-Openbridge-Token` header.

## Docker Direct Auth

The checked-in Docker workflow builds from local source and defaults to direct Amazon Ads auth.

Required `.env` values:

```bash
AUTH_METHOD=direct
PORT=9080
AMAZON_AD_API_CLIENT_ID="your-client-id"
AMAZON_AD_API_CLIENT_SECRET="your-client-secret"
AMAZON_AD_API_REFRESH_TOKEN="your-refresh-token"
```

Optional direct-auth values:

```bash
AMAZON_AD_API_PROFILE_ID="1234567890"
AMAZON_ADS_REGION="na"
OAUTH_REDIRECT_URI="http://localhost:9080/auth/callback"
AMAZON_ADS_TOKEN_PERSIST=true
```

Build and start the container:

```bash
docker compose build
docker compose up -d
docker compose logs -f amazon-ads-mcp
```

Focused checks:

```bash
curl http://localhost:9080/health
curl -i http://localhost:9080/mcp
docker compose ps
```

Persistence behavior:

- `cache` is mounted at `/app/.cache` for token and runtime cache data.
- The root compose file uses named Docker volumes so data survives container recreation until you remove the volumes.
- `docker-compose.local.yaml` bind-mounts `./data` and `./.cache` for local inspection.

To switch to OpenBridge:

```bash
AUTH_METHOD=openbridge OPENBRIDGE_REFRESH_TOKEN="your-openbridge-token" docker compose up -d
```

`AMAZON_ADS_AUTH_METHOD` is accepted as a legacy alias for `AUTH_METHOD`.

## Development

Required validation flow before committing:

```bash
uv run ruff check --fix
uv run pytest
docker build -t amazon-ads-mcp .
```
