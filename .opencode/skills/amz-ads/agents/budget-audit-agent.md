# Budget Audit Agent

Parallel audit agent for budget utilization analysis. Invoked by the `amz-ads` orchestrator when `parallel_agents: true`. All findings are advisory — the current MCP does not expose day-by-day budget history.

## Scope

Estimate budget utilization from aggregate keyword spend data and compare against declared daily budget values. Flag under-pacing and potentially budget-constrained campaigns.

## Inputs (from orchestrator)

- `campaign_map`: result of `list_campaigns` (contains daily_budget per campaign)
- `keyword_performance_data`: result of `get_keyword_performance`
- `date_range`: `start_date`, `end_date`

## Tasks

1. Count the number of days in the reporting window.
2. Aggregate total spend per campaign from keyword_performance_data.
3. Compute estimated daily spend = total_spend / days.
4. Compare to daily_budget from campaign_map:
   - Utilization < 50%: under-pacing — flag with possible causes (bid too low, low search volume, poor relevance)
   - Utilization 50–90%: normal range
   - Utilization > 90%: potentially budget-constrained — flag as advisory
5. Label ALL findings as advisory with explicit confidence note.
6. State the missing data sources explicitly.
7. Compute budget subscore (0–25 points, heavily penalized for confidence limitations).

## Confidence Limitations (Always State These)

- Daily budget history is not available: utilization is estimated from keyword spend aggregate, not true hourly pacing
- Impression share data is not available: cannot determine if budget ceiling is actually suppressing impressions
- Budget change history is not available: spend drop might reflect a budget reduction, not under-delivery

## Output Shape

```
budget_audit:
  subscore: <0–25>
  grade_note: <brief explanation, always notes advisory status>
  confidence: "advisory — no daily budget history available"
  campaigns: [{ campaign_id, campaign_name, daily_budget, total_spend, days, estimated_daily_spend, utilization_pct, status, notes }]
  under_pacing: [{ campaign_id, utilization_pct, possible_causes }]
  budget_constrained: [{ campaign_id, utilization_pct, note }]
  unsupported: [
    "day-by-day budget history: UNSUPPORTED",
    "impression share lost to budget: UNSUPPORTED",
    "automatic budget adjustment: no write tool available"
  ]
```
