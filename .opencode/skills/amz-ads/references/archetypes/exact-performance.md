# Archetype: Exact Performance Campaign

## Purpose

Extract maximum performance from proven, high-converting search terms. Exact match provides the tightest targeting and the best bid-control signal. This is the primary revenue driver in a healthy SP account.

## Targeting Type

MANUAL — EXACT match keywords only

## Expected Characteristics

| Property | Expected Value |
|---|---|
| Targeting type | Manual |
| Match types | EXACT only |
| Keyword list | Promoted from auto/broad discovery; proven converters |
| Bid strategy | Higher bids justified by known conversion rate |
| Daily budget | Higher (performance campaign) |
| ACoS | At or below target (should be the most efficient campaign type) |
| CTR | Highest of all campaign types |
| CVR | Highest of all campaign types |

## Signals That This Is Working

- ACoS at or below target ACoS
- CTR above account average
- CVR above account average
- Growing keyword list over time as more terms are promoted from discovery

## Red Flags

- ACoS equal to or higher than broad/phrase campaigns (loses the performance advantage)
- No new keywords added in 90+ days (discovery pipeline may be broken)
- Pause candidates growing — terms that were proven converters may have become stale
- Exact keywords also present in auto or broad campaigns without negation (bid war with yourself)

## Required Practices

- Source keywords only from proven discovery terms
- Monitor for ACoS drift — if a formerly great exact term degrades, investigate listing or seasonal changes
- Regularly review pause candidates (clicks ≥ 20, orders == 0)

## What the MCP Can Check

- Keyword list and bids: `list_campaigns`
- Performance metrics: `get_keyword_performance`
- Pause candidates: `get_keyword_performance` (clicks ≥ 20, orders == 0)
- Bid calibration: `adjust_keyword_bids` (after approval)
