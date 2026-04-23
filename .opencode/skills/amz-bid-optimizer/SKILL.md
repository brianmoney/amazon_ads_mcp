---
name: amz-bid-optimizer
description: 'Optimize Sponsored Products keyword bids using the target-ACoS method against live keyword performance data. Use when the user wants bid adjustment recommendations, wants to raise bids on under-spending profitable terms, or wants to reduce bids on over-spending terms. Produces bid adjustment recommendations with percentage changes; applies them only after user approval.'
argument-hint: 'Campaign IDs, date range, target ACoS (e.g. 0.30 for 30%)'
user-invocable: true
disable-model-invocation: false
---

# amz-bid-optimizer — Keyword Bid Optimization Workflow

Focused sub-skill for bid adjustment. Reads keyword performance, applies the target-ACoS bid formula, enforces Quality Gates, and produces an approval-gated adjustment set.

## MCP Tools Used

Read tools:
- `list_campaigns` — confirm campaign and keyword hierarchy
- `get_keyword_performance` — keyword metrics including current bids
- `sp_report_status` — poll async report if timeout occurs

Write tools (approval-gated):
- `adjust_keyword_bids` — apply approved bid changes

## Bid Adjustment Formula

```
suggested_bid = current_bid × (target_acos / actual_acos)
change_pct    = ((suggested_bid / current_bid) - 1) × 100
```

See `references/bid-adjustment-rules.md` for caps, floors, and scaling constraints.

## Procedure

1. Validate MCP readiness.
2. Call `list_campaigns` to get keyword IDs and current bid values.
3. Call `get_keyword_performance` for the requested range.
4. Apply attribution window check per `references/attribution.md`.
5. Apply minimum click threshold gate per `references/quality-gates.md` — do not adjust bids on keywords below the threshold.
6. Compute suggested bids per the formula above.
7. Apply bid adjustment caps and floors from `references/bid-adjustment-rules.md`.
8. Classify each keyword: raise / reduce / hold / pause-candidate.
9. Format recommendations per `references/recommendation-contract.md`.
10. Present the adjustment set for approval before calling `adjust_keyword_bids`.

## Unsupported

- Placement-level bid modifiers: not available in current MCP
- Dayparting adjustments: not available
- Portfolio-level bid strategy rules: not available

## References

Load from `../amz-ads/references/`:
`bid-adjustment-rules.md`, `acos-math.md`, `attribution.md`, `quality-gates.md`, `recommendation-contract.md`
