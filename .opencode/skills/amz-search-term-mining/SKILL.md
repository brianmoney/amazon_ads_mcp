---
name: amz-search-term-mining
description: 'Mine Sponsored Products search-term data for harvest, negation, and waste-reduction opportunities using the real MCP reporting surface.'
argument-hint: 'Date range, campaign scope, and whether the user wants harvest, negation, or both'
user-invocable: true
disable-model-invocation: false
---

# amz-search-term-mining

Use the real Sponsored Products search-term reporting flow only.

## Procedure

1. Read `../amz-ads/references/mcp-tool-surface.md`.
2. Validate auth, active profile, and region.
3. Use `get_search_term_report` for evidence and `sp_report_status` if the report is still in flight.
4. Separate harvest candidates, negative candidates, and inconclusive rows clearly.
5. Wait for approval before calling `add_keywords` or `negate_keywords`.
