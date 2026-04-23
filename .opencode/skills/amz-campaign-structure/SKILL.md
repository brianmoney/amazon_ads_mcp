---
name: amz-campaign-structure
description: 'Review Sponsored Products campaign hierarchy and keyword targeting structure for archetype alignment, match-type coverage, and structural anti-patterns. Use when the user wants to understand whether campaigns follow the recommended auto-research → manual-discovery → exact-performance funnel, identify campaigns with missing match types, or find structural issues like single-ad-group campaigns with mixed intent.'
argument-hint: 'Campaign IDs to review'
user-invocable: true
disable-model-invocation: false
---

# amz-campaign-structure — Campaign Hierarchy and Targeting Review

Focused sub-skill for structural analysis. Inspects campaign hierarchy and keyword targeting against archetype patterns without requiring historical performance data.

## MCP Tools Used

Read tools:
- `list_campaigns` — full campaign and ad group hierarchy with keyword targeting types
- `get_keyword_performance` — match-type distribution and performance by targeting type (optional, enriches structural findings)

No write tools — structure recommendations are advisory only.

## Procedure

1. Validate MCP readiness.
2. Call `list_campaigns` to retrieve full hierarchy.
3. Map each campaign to an archetype from `references/archetypes/`:
   - `auto-research.md`
   - `manual-discovery.md`
   - `exact-performance.md`
   - `product-targeting.md`
   - `brand-defense.md`
4. Identify structural gaps:
   - Missing auto research campaign (no discovery funnel)
   - Broad/phrase and exact in the same ad group (mixed intent)
   - Auto campaign with no negatives (bleed risk)
   - Single-keyword ad groups where multi-match coverage is intended
   - Exact-only campaigns with no discovery source
5. Optionally enrich with `get_keyword_performance` to show match-type distribution and performance.
6. Format recommendations per `references/recommendation-contract.md`.
7. Label findings as advisory (structural changes require campaign setup outside current write tools).

## Unsupported (Explicit)

- Creating new campaigns or ad groups: **UNSUPPORTED** — no campaign creation tool in current MCP
- Archiving campaigns: **UNSUPPORTED** — no campaign archive tool
- Moving keywords between ad groups: **UNSUPPORTED**

## References

Load from `../amz-ads/references/`:
`match-type-strategy.md`, `recommendation-contract.md`

Load from `../amz-ads/references/archetypes/` as needed for archetype comparison.
