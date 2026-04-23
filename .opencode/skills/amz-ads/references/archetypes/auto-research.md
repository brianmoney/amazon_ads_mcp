# Archetype: Auto Research Campaign

## Purpose

Discover new search terms at low cost. Auto targeting lets Amazon decide which queries to show ads for based on product listing content. Primary function is to feed the manual funnel with converting search terms.

## Targeting Type

AUTO (Amazon controls targeting — no keyword list)

## Expected Characteristics

| Property | Expected Value |
|---|---|
| Targeting type | Auto |
| Keyword list | None (auto targeting handles this) |
| Match type | N/A |
| Bid strategy | Usually low conservative bid |
| Daily budget | Lower than manual campaigns |
| ACoS | Higher than account average (discovery tax acceptable) |
| CTR | Lower than manual (broad targeting includes irrelevant traffic) |

## Signals That This Is Working

- Search-term report surfaces new converting queries not yet in manual campaigns
- New harvest candidates appear after each reporting cycle
- CTR improving over time as negatives are added

## Red Flags

- Zero negatives after 30+ days of run time (no waste control)
- ACoS > 3× target with no harvest candidates found (off-target product listing)
- Duplicating exact terms already in a performance campaign (bid conflict)

## Required Practices

- Add campaign-level negatives regularly (from search-term waste analysis)
- Review harvest candidates every 14–30 days
- Set low bids — this campaign is for discovery, not performance

## What the MCP Can Check

- Presence of auto-targeting campaign: `list_campaigns`
- Search-term waste and harvest: `get_search_term_report`
- Negative keywords at campaign level: `list_campaigns` (negative targeting state visible in campaign data)
- Bleed volume: `get_keyword_performance` match-type distribution

## What the MCP Cannot Check

- Amazon's internal query-to-product match quality
- Impression share for auto targeting
