---
name: amz-budget-pacing
description: 'Analyze Sponsored Products campaign budget utilization and flag campaigns at risk of running out of budget or under-spending. Advisory only in phase 1 — the current MCP surface does not expose day-by-day budget history, so all findings carry limited confidence. Use when the user wants to understand which campaigns may be budget-constrained or under-pacing.'
argument-hint: 'Campaign IDs and the analysis window'
user-invocable: true
disable-model-invocation: false
---

# amz-budget-pacing — Budget Utilization Analysis (Advisory)

Advisory sub-skill for budget analysis. Uses campaign-level spend from keyword performance data as a proxy for pacing. All budget findings are labeled advisory because the MCP does not expose day-by-day budget history or current daily budget utilization signals.

## MCP Tools Used

Read tools:
- `list_campaigns` — retrieve daily budget values
- `get_keyword_performance` — aggregate spend across the reporting window

No write tools are called by this sub-skill. Budget changes must be made outside the MCP.

## Procedure

1. Validate MCP readiness.
2. Call `list_campaigns` to get daily budget for each campaign.
3. Call `get_keyword_performance` for the requested range.
4. Aggregate total spend per campaign over the window.
5. Compute estimated daily spend = total spend / number of days.
6. Compare estimated daily spend to daily budget:
   - Utilization < 50%: flag as under-pacing (may be limited by bids, relevance, or low search volume)
   - Utilization 50–90%: normal range
   - Utilization > 90%: flag as potentially budget-constrained
7. Label all findings as advisory with confidence note.
8. State explicitly that day-by-day budget history and impression-share data are not available.

## Unsupported (Explicit)

- Day-by-day budget utilization curves: **UNSUPPORTED** — no budget history API in current MCP
- Impression share / lost impression share due to budget: **UNSUPPORTED**
- Automatic budget increase recommendations: **NOT APPLY-READY** — no budget write tool available
- Portfolio budget management: **UNSUPPORTED**

See `docs/amz-missing-information.md` for the expansion roadmap.

## References

Load from `../amz-ads/references/`:
`quality-gates.md`, `recommendation-contract.md`
