# Archetype: Product Targeting Campaign

## Purpose

Target specific competitor ASINs or product categories with ASIN or category targeting instead of keyword targeting. Captures shoppers browsing competitor product pages or category pages.

## Targeting Type

MANUAL — Product targeting (ASIN or category targets, not keyword-based)

## Expected Characteristics

| Property | Expected Value |
|---|---|
| Targeting type | Product / ASIN |
| Keyword list | None (ASIN or category targets) |
| Bid strategy | Moderate — competing for placement on competitor pages |
| Daily budget | Mid-tier |
| ACoS | Often higher than keyword campaigns (lower purchase intent) |
| CTR | Lower than keyword campaigns |
| CVR | Lower than keyword campaigns |

## Signals That This Is Working

- Impressions on relevant competitor product pages
- Steady trickle of orders at acceptable ACoS
- Growing awareness of product as alternative to targeted competitor

## Red Flags

- ASIN targets with zero impressions (product may be unavailable or category mismatch)
- Very high ACoS with no sign of improving (competitive product too dominant)
- Competing against your own ASINs (internal cannibalization)

## Phase 1 MCP Limitation

**ASIN-level product targeting detail is partially limited** in the current MCP surface. `list_campaigns` returns campaign and ad group structure but may not expose individual ASIN target IDs in all cases. Verify what data is available from your specific MCP version before drawing structural conclusions.

## What the MCP Can Check

- Campaign presence and ad group structure: `list_campaigns`
- Campaign-level performance: `get_keyword_performance` (aggregated)

## What the MCP Cannot Check

- Which specific ASINs are being targeted
- Impression share on specific competitor pages
- Organic rank of targeted competitors
