# Archetype: Brand Defense Campaign

## Purpose

Protect brand search terms from competitor conquest. Ensure that when a shopper searches for the brand name, the brand's own ad appears first. Often the highest ROAS campaign in the account.

## Targeting Type

MANUAL — EXACT match on brand name and brand + product variant keywords

## Expected Characteristics

| Property | Expected Value |
|---|---|
| Targeting type | Manual |
| Match types | EXACT (brand terms); optional PHRASE for brand + modifier |
| Keyword list | Brand name, brand + product type, brand + key variants |
| Bid strategy | Aggressive — never let a competitor take brand queries |
| Daily budget | Sufficient to never run out on peak days |
| ACoS | Typically very low (brand queries have high purchase intent) |
| CTR | Very high |
| CVR | Highest of all campaign types |

## Signals That This Is Working

- Very low ACoS (often 5–15%)
- High CVR
- Campaign budget never runs out

## Red Flags

- Brand terms appearing in auto or broad campaigns without being negated there (double-serving your own brand)
- Budget running out before end of day
- ACoS climbing — could indicate competitor bidding on brand terms creating impression-share competition

## Required Practices

- Set bids high enough to consistently win brand impressions
- Never reduce bids on brand terms without explicit approval (see bid-adjustment-rules.md floor policy)
- Negate brand terms from auto and broad discovery campaigns to prevent split attribution

## What the MCP Can Check

- Brand campaign presence and keyword list: `list_campaigns`
- ACoS and performance: `get_keyword_performance`
- Budget utilization (advisory): `amz-budget-pacing`

## What the MCP Cannot Check

- Whether competitors are bidding on your brand terms
- Impression share on brand queries
- Organic rank for brand terms
