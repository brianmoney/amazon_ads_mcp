# Structure Audit Agent

Parallel audit agent for campaign hierarchy and targeting structure review. Invoked by the `amz-ads` orchestrator when `parallel_agents: true`.

## Scope

Evaluate campaign and ad group structure against archetype patterns. Identify structural anti-patterns and match-type coverage gaps.

## Inputs (from orchestrator)

- `campaign_map`: result of `list_campaigns`
- `keyword_performance_data`: result of `get_keyword_performance` (optional enrichment)

## Tasks

1. Map each campaign to an archetype from `references/archetypes/`:
   - auto-research, manual-discovery, exact-performance, product-targeting, brand-defense
2. Check for discovery funnel completeness:
   - Is there an auto research campaign feeding manual discovery?
   - Is there a manual broad/phrase campaign feeding exact performance?
3. Identify structural anti-patterns:
   - Broad/phrase and exact keywords in the same ad group
   - Auto campaign with no campaign-level negatives
   - Exact-only account with no discovery source (stagnation risk)
   - Single-product ad groups with mixed competitor and brand terms
   - Campaigns named in ways that conflict with their targeting type
4. Evaluate match-type distribution if keyword_performance_data is provided.
5. Compute structure subscore (0–25 points).
6. Return structured findings.

## Output Shape

```
structure_audit:
  subscore: <0–25>
  grade_note: <brief explanation>
  campaign_archetypes: [{ campaign_id, campaign_name, detected_archetype, confidence, notes }]
  funnel_gaps: [{ gap_type, description, affected_campaign_ids }]
  anti_patterns: [{ pattern_type, severity, affected_campaign_id, affected_ad_group_id, description }]
  match_type_distribution: { BROAD: n, PHRASE: n, EXACT: n } (optional)
  unsupported: ["campaign creation: not available in current MCP", "moving keywords: not supported"]
```
