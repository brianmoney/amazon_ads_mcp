---
name: amz-budget-pacing
description: 'Analyze Sponsored Products budget pacing using the live campaign budget history surface and keep budget changes approval-gated.'
argument-hint: 'Date range, campaign scope, and whether the goal is diagnosis or budget-change recommendations'
user-invocable: true
disable-model-invocation: false
---

# amz-budget-pacing

Use pacing history when available and keep missing-data limits explicit.

## Procedure

1. Read `../amz-ads/references/mcp-tool-surface.md`.
2. Validate auth, active profile, and region.
3. Use `get_campaign_budget_history` for pacing evidence.
4. If pacing history is unavailable or incomplete for the requested scope, mark the pacing conclusion blocked or advisory instead of inventing coverage.
5. Wait for approval before calling `update_campaign_budget`.
