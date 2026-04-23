# Search-Term Audit Agent

Parallel audit agent for search-term analysis. Invoked by the `amz-ads` orchestrator when `parallel_agents: true`.

## Scope

Analyze search-term report data for waste, harvest opportunities, and bleed from auto/broad targeting into unwanted queries.

## Inputs (from orchestrator)

- `search_term_data`: result of `get_search_term_report`
- `campaign_map`: result of `list_campaigns`
- `target_acos`: advertiser target as decimal
- `date_range`: `start_date`, `end_date`

## Tasks

1. Apply minimum-volume thresholds per `references/quality-gates.md`.
2. Check attribution window per `references/attribution.md`.
3. For each search term, determine existing targeting state from the report data:
   - Already exact-match targeted
   - Only auto or broad targeted
   - Not targeted at all (new discovery)
4. Classify terms per `references/search-term-rules.md`:
   - **Harvest**: ACoS ≤ target AND clicks ≥ threshold AND not already exact-targeted
   - **Waste / negate**: spend > waste threshold AND orders == 0 AND clicks ≥ threshold
   - **Monitor**: positive signal but below minimum volume
   - **Irrelevant**: clearly off-topic (flag for manual review)
5. Compute search-term hygiene subscore (0–25 points).
6. Return structured findings.

## Output Shape

```
search_term_audit:
  subscore: <0–25>
  grade_note: <brief explanation>
  harvest_candidates: [{ search_term, source_campaign_id, source_ad_group_id, acos, clicks, orders, recommended_match_type, reason }]
  negate_candidates: [{ search_term, source_campaign_id, source_ad_group_id, spend, clicks, orders, negate_level, reason }]
  monitor_terms: [{ search_term, clicks, spend, note }]
  gates_passed: [...]
  gates_blocked: [{ gate, reason }]
  unsupported: ["placement-level filtering: no placement report available"]
```
