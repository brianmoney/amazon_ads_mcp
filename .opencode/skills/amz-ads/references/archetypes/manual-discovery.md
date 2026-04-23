# Archetype: Manual Discovery Campaign

## Purpose

Test new keyword themes with moderate control. Broad and phrase match keywords allow variation while keeping some relevance guardrails. Primary function is to validate themes from auto research and promote proven terms to exact.

## Targeting Type

MANUAL — BROAD and PHRASE match keywords

## Expected Characteristics

| Property | Expected Value |
|---|---|
| Targeting type | Manual |
| Match types | BROAD and/or PHRASE |
| Keyword list | Themes sourced from auto research harvests or known product themes |
| Bid strategy | Moderate — higher than auto, lower than exact |
| Daily budget | Mid-tier |
| ACoS | Slightly above target (discovery overhead expected) |
| CTR | Moderate |

## Signals That This Is Working

- BROAD/PHRASE keywords generating search terms with good conversion signals
- Regular harvest of exact match candidates for promotion
- ACoS within 1.2–1.5× target range

## Red Flags

- Broad keywords generating zero exact-match harvests after 30+ days
- ACoS > 2× target with high spend (theme mismatch or no negatives)
- Same search terms appearing in both this campaign and the auto campaign without negation in auto (double-spend)

## Required Practices

- Add negative keywords for irrelevant themes
- Review search-term reports every 14–30 days to find exact candidates
- Cross-negate: if a search term converts well in this campaign and is promoted to exact, negate it from auto to prevent bid conflict

## What the MCP Can Check

- Keyword list and match types: `list_campaigns`
- Search terms generated: `get_search_term_report`
- ACoS and performance: `get_keyword_performance`
- Negative state: `list_campaigns`

## What the MCP Cannot Check

- Whether a term is double-covered without cross-referencing exact campaign keyword lists (requires manual comparison)
