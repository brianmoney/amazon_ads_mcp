# Keyword Audit Agent

Parallel audit agent for keyword-level analysis. Invoked by the `amz-ads` orchestrator when `parallel_agents: true`.

## Scope

Analyze keyword performance metrics across all campaigns in scope. Identify efficiency outliers, bid calibration issues, and pause candidates.

## Inputs (from orchestrator)

- `keyword_performance_data`: result of `get_keyword_performance`
- `campaign_map`: result of `list_campaigns`
- `target_acos`: advertiser target as decimal
- `date_range`: `start_date`, `end_date`

## Tasks

1. Compute per-keyword metrics: CTR, CPC, CVR, ACoS, ROAS per `references/acos-math.md`.
2. Skip keywords with zero impressions.
3. Apply minimum-volume gates per `references/quality-gates.md` before drawing any conclusions.
4. Check attribution window per `references/attribution.md`.
5. Classify each keyword:
   - **Bid-reduce**: ACoS > target_acos × 1.5 AND clicks ≥ threshold
   - **Bid-raise**: ACoS < target_acos × 0.7 AND spend < 50% of ad group average
   - **Pause candidate**: clicks ≥ 20 AND orders == 0, OR spend > 2× AOV AND orders == 0
   - **Hold**: within acceptable range
   - **Insufficient data**: below minimum-volume threshold
6. Compute bid suggestions for bid-reduce and bid-raise keywords per `references/bid-adjustment-rules.md`.
7. Return structured findings:
   - Keyword efficiency subscore (0–25 points for health score)
   - Classified keyword list with suggested actions
   - Bid adjustment set (for orchestrator to present for approval)

## Output Shape

```
keyword_audit:
  subscore: <0–25>
  grade_note: <brief explanation>
  bid_reduce: [{ keyword_id, keyword_text, match_type, current_bid, suggested_bid, change_pct, acos, clicks, reason }]
  bid_raise:  [{ keyword_id, keyword_text, match_type, current_bid, suggested_bid, change_pct, acos, clicks, reason }]
  pause_candidates: [{ keyword_id, keyword_text, match_type, clicks, spend, orders, reason }]
  insufficient_data: [{ keyword_id, keyword_text, clicks, reason }]
  gates_passed: [...]
  gates_blocked: [{ gate, reason }]
```
