---
name: amz-search-term-mining
description: 'Mine Sponsored Products search terms to identify waste, harvest converting terms as new manual keywords, and build negative keyword lists. Use when the user wants to find wasted spend search terms, promote top search terms to exact or phrase match, or clean up auto or broad campaign bleed.'
argument-hint: 'Campaign IDs, date range, target ACoS, and whether to also produce a negative keyword list'
user-invocable: true
disable-model-invocation: false
---

# amz-search-term-mining — Search Term Waste and Harvest Workflow

Focused sub-skill for search-term analysis. Pulls search-term report data, classifies each term against waste and harvest rules, and produces an approved-gated keyword and negative list.

## MCP Tools Used

Read tools:
- `list_campaigns` — verify campaign structure and ad group IDs
- `get_search_term_report` — search term traffic, conversions, and existing targeting state
- `sp_report_status` — poll async report if timeout occurs

Write tools (approval-gated):
- `add_keywords` — promote harvested terms to manual campaigns
- `negate_keywords` — block wasted terms from auto/broad campaigns

## Procedure

1. Validate MCP readiness.
2. Call `list_campaigns` to map campaign and ad group IDs.
3. Call `get_search_term_report` for the requested range.
4. Apply minimum-volume thresholds per `references/quality-gates.md`.
5. Classify each search term per `references/search-term-rules.md`:
   - Harvest candidates: clicks ≥ threshold and ACOS ≤ target
   - Waste candidates: clicks ≥ threshold and ACOS > waste_multiplier × target, or spend > 0 and orders == 0
   - Already targeted: term already exists as an exact keyword (no action needed)
6. Check attribution window before drawing waste conclusions per `references/attribution.md`.
7. Format output per `references/recommendation-contract.md`.
8. Present harvest list and negative list for user approval before calling write tools.

## Unsupported

- Placement-level search term filtering: not available (no placement report)
- Cross-campaign negative coordination at portfolio level: not supported in current MCP

## References

Load from `../amz-ads/references/`:
`search-term-rules.md`, `attribution.md`, `quality-gates.md`, `recommendation-contract.md`
