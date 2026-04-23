# Search-Term Decision Rules Reference

Used by: `amz-search-term-mining`, `amz-sp-audit`, `search-term-audit-agent`.

## Minimum Volume Thresholds

Before classifying any search term, apply these gates. Terms below threshold are labeled "insufficient data" and excluded from waste / harvest decisions.

| Decision | Minimum Clicks | Minimum Impressions |
|---|---|---|
| Harvest (add as keyword) | 3 | 50 |
| Waste / negate | 10 | — |
| Monitor (flag for later) | 1 | 10 |

These thresholds assume a 14-day or longer reporting window. Scale proportionally for shorter windows (but always require attribution window compliance first — see `attribution.md`).

## Classification Rules

### Harvest Candidate

A search term is a harvest candidate when ALL of the following are true:
- Clicks ≥ 3 (minimum harvest threshold)
- ACoS ≤ target ACoS (term is profitable)
- Term is NOT already exact-match targeted in any active keyword
- Reporting window ≥ 14 days

**Recommended action**: Add as EXACT match keyword in the corresponding manual/exact campaign. Optionally add as PHRASE in discovery campaign.

### Waste / Negate Candidate

A search term is a negate candidate when ANY of the following are true:
- Clicks ≥ 10 AND orders == 0 AND spend > 0
- Spend > 2× average order value AND orders == 0
- ACoS > 3× target AND clicks ≥ 10

**Negate level**:
- Apply at **campaign level** when the term bleeds across multiple ad groups in the same campaign
- Apply at **ad group level** when waste is isolated to one ad group

**Caution**: check attribution window before negating — a term with recent clicks may still convert.

### Already Targeted

A search term appears in the already-targeted list when:
- It matches an existing EXACT keyword in an active ad group

No action needed. Note this in output to avoid duplicate recommendations.

### Monitor

Terms that have impressions or clicks but are below minimum thresholds for harvest or negate decisions. Flag for re-evaluation after the next reporting cycle.

### Irrelevant

Terms that are clearly unrelated to the advertised product (e.g., competitor brand name in a generic product campaign, or obvious category mismatch). Flag for manual review before negating — automated negation of brand terms requires human judgment.

## Output Precedence

When a term qualifies for both harvest and waste:
- Harvest takes precedence if the ACoS condition is met
- If ACoS is below target but volume is very low, classify as Monitor, not Harvest

## Bleed Patterns

Common search-term bleed to look for in auto campaigns:
- Generic queries with no product relevance
- Competitor brand terms (check if intentional)
- Questions and informational queries (low purchase intent)
- Spelling variants that the advertiser has already targeted

## Tools Sourcing This Analysis

- `get_search_term_report`: provides search_term, matchType, keywordText, impressions, clicks, cost, sales14d, purchases14d, adGroupId, campaignId
