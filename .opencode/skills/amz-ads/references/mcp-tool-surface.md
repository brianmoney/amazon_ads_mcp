# MCP Tool Surface Reference — Sponsored Products

Used by: all `amz-*` skills and audit agents.

This file documents the live tool and prompt names exposed by the `amazon-ads` MCP server as of this skill family's creation. Always verify against the running server before assuming availability.

## Read Tools (Safe to Call Without Approval)

| Tool Name | MCP Call | Purpose |
|---|---|---|
| `list_campaigns` | `mcp_amazon-ads_list_campaigns` | List SP campaigns with nested ad groups; paginate with `limit`/`offset` |
| `get_keyword_performance` | `mcp_amazon-ads_get_keyword_performance` | Keyword metrics for a date range; supports `resume_from_report_id` for async recovery |
| `get_search_term_report` | `mcp_amazon-ads_get_search_term_report` | Search term traffic with targeting context; supports `resume_from_report_id` |
| `sp_report_status` | `mcp_amazon-ads_sp_report_status` | Check async report lifecycle by `report_id` |

## Write Tools (Approval-Gated — Never Auto-Apply)

| Tool Name | MCP Call | Purpose | Requires Approval |
|---|---|---|---|
| `adjust_keyword_bids` | `mcp_amazon-ads_adjust_keyword_bids` | Bulk keyword bid updates | Yes |
| `add_keywords` | `mcp_amazon-ads_add_keywords` | Add new keywords to an ad group | Yes |
| `negate_keywords` | `mcp_amazon-ads_negate_keywords` | Add negative exact keywords | Yes |
| `pause_keywords` | `mcp_amazon-ads_pause_keywords` | Pause keyword IDs | Yes |

## Identity and Auth Utility Tools

| Tool Name | Purpose |
|---|---|
| `set_active_identity` | Switch between stored credentials |
| `get_active_identity` | Show the current identity |
| `list_identities` | List all available identities |
| `set_active_profile` | Set the active advertiser profile |
| `get_active_profile` | Get the current profile |
| `clear_active_profile` | Clear the active profile |
| `select_profile` | Interactive profile selection |
| `summarize_profiles` | Profile list summary |
| `search_profiles` | Search profiles by name or ID |
| `page_profiles` | Paginate large profile lists |
| `refresh_profiles_cache` | Force-refresh cached profile list |
| `set_region` | Set the API region (NA, EU, FE) |
| `get_region` | Get the current region |
| `list_regions` | List available regions |
| `get_routing_state` | Show routing state summary |
| `check_oauth_status` | Check access token validity |
| `refresh_oauth_token` | Refresh an expired access token |
| `start_oauth_flow` | Start OAuth authorization |
| `clear_oauth_tokens` | Clear stored OAuth tokens |
| `test_sampling` | Test sampling middleware |

## Built-in Workflow Prompts

| Prompt Name | Purpose |
|---|---|
| `sp_bid_optimization` | SP bid optimization workflow prompt |
| `sp_search_term_harvesting` | SP search term harvesting workflow prompt |
| `auth_profile_setup` | Auth and profile setup prompt |
| `troubleshoot_auth_or_routing` | Auth and routing troubleshooting |
| `setup_region` | Region setup prompt |

## Supported SP Workflows

| Workflow | Read Tools Required | Write Tools (After Approval) |
|---|---|---|
| Campaign hierarchy audit | `list_campaigns` | None |
| Keyword performance analysis | `get_keyword_performance` | None |
| Search-term waste/harvest | `get_search_term_report` | `add_keywords`, `negate_keywords` |
| Bid optimization | `get_keyword_performance`, `list_campaigns` | `adjust_keyword_bids` |
| Pause keyword cleanup | `get_keyword_performance` | `pause_keywords` |
| Full SP audit | All 4 read tools | All 4 write tools (after approval) |
| Async report recovery | `sp_report_status` | None |

## Unsupported Areas (Phase 1)

These workflows are NOT supported by the current MCP surface. Every skill must surface these as explicitly unsupported, not as passed or skipped gates:

| Missing Capability | Impact |
|---|---|
| Sponsored Brands (SB) tools | Cannot audit SB campaigns, creatives, or performance |
| Sponsored Display (SD) tools | Cannot audit SD campaigns or audience targeting |
| Placement-level metrics | Cannot analyze top-of-search vs. product page performance; no placement bid modifier recommendations |
| Day-by-day budget history | Cannot compute true pacing curves; budget analysis is advisory only |
| Impression share data | Cannot compute lost impression share (budget or rank) |
| Organic rank signals | Cannot evaluate halo effect or organic protection |
| Listing quality signals | Cannot diagnose low CTR caused by listing issues |
| Category benchmark data | Cannot compare ACoS against category averages |
| Portfolio-level budget rules | Cannot manage or inspect portfolio budgets |
| Campaign creation / archiving | Cannot create new campaigns or ad groups; cannot archive campaigns |
| Campaign budget update | No write tool for daily budget changes |

See `docs/amz-missing-information.md` for the expansion roadmap and recommended future MCP additions.

## Async Report Handling Notes

Both `get_keyword_performance` and `get_search_term_report` are async-capable:
- If the tool times out and returns a `report_id`, use `sp_report_status` to poll
- Wait 15–30 seconds between polls to avoid burning API quota
- When status is `COMPLETED`, re-call the original tool with `resume_from_report_id`
- Signed download URLs in status response expire — refresh with another `sp_report_status` call if download returns `403`
