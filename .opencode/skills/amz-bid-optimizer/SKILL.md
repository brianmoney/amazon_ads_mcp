---
name: amz-bid-optimizer
description: 'Generate Sponsored Products bid recommendations from the live MCP performance surface and keep bid changes approval-gated.'
argument-hint: 'Date range, campaign scope, and target ACOS or efficiency goal'
user-invocable: true
disable-model-invocation: false
---

# amz-bid-optimizer

Ground bid guidance in live Sponsored Products evidence.

## Procedure

1. Read `../amz-ads/references/mcp-tool-surface.md`.
2. Validate auth, active profile, and region.
3. Use `get_keyword_performance` and `get_placement_report` when placement context matters.
4. Keep findings read-first and cite the source read tools for every bid recommendation.
5. Wait for approval before calling `adjust_keyword_bids`.
