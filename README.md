# Amazon Ads MCP

Amazon Ads MCP is a Python MCP server that provides Amazon Ads authentication, profile and region management, and a purpose-built set of Sponsored Products and Sponsored Display tools for reporting and campaign operations.

## Source Of Truth

This README is intended to be the human-readable source of truth for the MCP surface exposed to agent clients.

It is derived from the server registration code in:

- `src/amazon_ads_mcp/server/builtin_tools.py`
- `src/amazon_ads_mcp/tools/sp/__init__.py`
- `src/amazon_ads_mcp/tools/portfolio/__init__.py`
- `src/amazon_ads_mcp/tools/sd/__init__.py`
- `src/amazon_ads_mcp/server/builtin_prompts.py`

The server does not expose the legacy OpenAPI-generated tool catalog, download/export tools, or code-mode helpers.

## Server Surface

### Always-Available Utility Tools

- `set_active_profile` — Set the active Amazon Ads profile ID used for API calls.
- `get_active_profile` — Return the currently active profile ID.
- `clear_active_profile` — Clear the active profile selection.
- `select_profile` — Interactively choose a profile through MCP elicitation when the profile list is small enough to display safely.
- `summarize_profiles` — Summarize available profiles by country and account type.
- `search_profiles` — Search profiles by Amazon legal account name or profile ID, with optional country and account-type filters. When a brand alias differs from the underlying Amazon name, narrow by country and search with the legal name or profile ID.
- `page_profiles` — Page through profiles with bounded `offset` and `limit` output.
- `refresh_profiles_cache` — Refresh cached profiles for the current auth context and region.
- `set_region` — Set the region used for Amazon Ads API routing.
- `get_region` — Return the current region setting.
- `list_regions` — List the supported routing regions.
- `get_routing_state` — Return the effective routing state, including region, resolved host, headers, and sandbox mode.

### Sponsored Products Tools

- `list_campaigns` — List Sponsored Products campaigns with nested ad-group and nullable portfolio context. `campaign_states` accepts `ENABLED`, `PAUSED`, or `ARCHIVED`, normalizes values to uppercase, and leaves the listing unfiltered by state when omitted.
- `get_campaign_budget_history` — Run or resume an async Sponsored Products budget history report and return daily budget pacing and utilization context. `timeout_seconds` bounds server-side polling for the current call; preserve the returned `report_id` and continue with `resume_from_report_id` instead of creating a duplicate report.
- `get_impression_share_report` — Run or resume an async Sponsored Products top-of-search impression share report with explicit availability diagnostics. `timeout_seconds` bounds server-side polling for the current call; preserve the returned `report_id` and continue with `resume_from_report_id` instead of creating a duplicate report.
- `get_keyword_performance` — Run or resume an async Sponsored Products keyword report with derived metrics such as ACOS, ROAS, CPC, and CTR. The current tool returns manual keyword rows only, so auto-targeting campaigns can legitimately return zero rows. `timeout_seconds` bounds server-side polling for the current call; preserve the returned `report_id` and continue with `resume_from_report_id` instead of creating a duplicate report.
- `get_placement_report` — Run or resume an async Sponsored Products placement report with current placement multipliers. `timeout_seconds` bounds server-side polling for the current call; preserve the returned `report_id` and continue with `resume_from_report_id` instead of creating a duplicate report.
- `get_search_term_report` — Run or resume an async Sponsored Products search-term report with manual-keyword and negative-keyword context. `timeout_seconds` bounds server-side polling for the current call; preserve the returned `report_id` and continue with `resume_from_report_id` instead of creating a duplicate report.
- `sp_report_status` — Check the lifecycle state of a previously created Sponsored Products async report by report ID.
- `adjust_keyword_bids` — Apply batch Sponsored Products keyword bid changes and return audit details. `adjustments` is a required non-empty list of `{ keyword_id, new_bid, reason? }`, the current bid bounds are `0.02` to `100.00`, and `previous_bid` or `prior_bid` reflects the live preflight bid observed at write time.
- `add_keywords` — Create Sponsored Products keywords while detecting duplicates. Required inputs are `campaign_id`, `ad_group_id`, and keyword items shaped like `{ keyword_text, bid, match_type? }`, with supported match types `EXACT`, `PHRASE`, and `BROAD` and bid bounds `0.02` to `100.00`.
- `negate_keywords` — Create negative exact Sponsored Products keywords at the campaign or ad-group level.
- `pause_keywords` — Pause Sponsored Products keywords with no-op detection.
- `update_campaign_budget` — Update a Sponsored Products campaign daily budget and return audit details.

### Portfolio Tools

- `list_portfolios` — List portfolios with normalized budget settings for the active profile and region.
- `get_portfolio_budget_usage` — Return current spend-versus-cap usage for requested portfolios with explicit availability diagnostics.
- `update_portfolio_budget` — Update a portfolio daily or monthly budget and return applied, skipped, or failed audit details. Use `budget_scope=daily` for an always-on cap, or `budget_scope=monthly` with both `start_date` and `end_date` for a date-range budget.

### Sponsored Display Tools

- `list_sd_campaigns` — List Sponsored Display campaigns with targeting-group context.
- `get_sd_performance` — Run or resume an async Sponsored Display targeting-group performance report with derived metrics. `timeout_seconds` bounds server-side polling for the current call; preserve the returned `report_id` and continue with `resume_from_report_id` instead of creating a duplicate report.
- `sd_report_status` — Check the lifecycle state of a previously created Sponsored Display async report by report ID so callers can resume with `get_sd_performance` instead of creating a duplicate report.

### Conditional Tools

These tools are registered only when the corresponding auth or runtime mode is enabled.

- `start_oauth_flow` — Start the Amazon Ads OAuth authorization flow. Available only with direct auth.
- `check_oauth_status` — Inspect current OAuth authentication state. Available only with direct auth.
- `refresh_oauth_token` — Manually refresh the OAuth access token. Available only with direct auth.
- `clear_oauth_tokens` — Clear stored OAuth tokens and OAuth state. Available only with direct auth.
- `set_active_identity` — Set the active OpenBridge identity used for downstream Amazon Ads calls. Available only with OpenBridge auth.
- `get_active_identity` — Return the current OpenBridge identity selection. Available only with OpenBridge auth.
- `list_identities` — List OpenBridge identities available to the current token. Available only with OpenBridge auth.
- `test_sampling` — Exercise MCP sampling support and optional server-side fallback. Available only when sampling is enabled.

### Workflow Prompts

These are MCP prompts, not tools.

- `auth_profile_setup` — Guide direct-auth users through OAuth, region setup, profile discovery, and profile activation.
- `troubleshoot_auth_or_routing` — Diagnose auth, profile, identity, and routing issues based on the current auth mode.
- `setup_region` — Guide region selection and routing verification.
- `sp_bid_optimization` — Guide a bounded Sponsored Products bid-optimization workflow using the supported read and write tools.
- `sp_search_term_harvesting` — Guide a Sponsored Products search-term harvesting and negation workflow using the supported read and write tools.

## Quick Start

Install dependencies:

```bash
uv sync
```

### Run The Server Yourself

Choose one startup method, not both.

Docker:

```bash
docker compose build
docker compose up -d
```

Local process:

```bash
uv run python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
```

The GitHub and package name is `amazon-ads-mcp`, but the Python module path is `amazon_ads_mcp`, so `python -m` commands use underscores, not hyphens.

If you prefer the installed console script name instead of `python -m`, this also works:

```bash
uv run amazon-ads-mcp --transport http --port 9080
```

### Let Claude Manage The Server Process

Instead of starting the server yourself, you can register the command directly with Claude. In that mode, do not separately run Docker or a local `uv run` server on the same port.

```bash
claude mcp add amazon-ads-mcp -- uv run amazon-ads-mcp --transport http --port 9080
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
