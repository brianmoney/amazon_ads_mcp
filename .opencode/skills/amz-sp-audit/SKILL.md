---
name: amz-sp-audit
description: 'Review Sponsored Products performance using the live Amazon Ads MCP reads and return grounded findings before any mutations are proposed.'
argument-hint: 'Date range, optional campaign scope, and optimization goal'
user-invocable: true
disable-model-invocation: false
---

# amz-sp-audit

Keep this workflow grounded in the live Sponsored Products read surface.

## Procedure

1. Read `../amz-ads/references/mcp-tool-surface.md`.
2. Validate auth, active profile, and region.
3. Use `list_campaigns`, `get_keyword_performance`, `get_search_term_report`, `get_impression_share_report`, `get_placement_report`, and `get_campaign_budget_history` when they fit the request.
4. Use `sp_report_status` when a Sponsored Products report stays in flight.
5. Return findings first, with each recommendation tied to the real MCP reads used.
6. Do not call write tools until the user approves the proposed actions.
