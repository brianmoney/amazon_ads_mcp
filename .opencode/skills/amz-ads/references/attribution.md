# Attribution Windows Reference

Used by: all SP sub-skills and audit agents.

## Amazon Sponsored Products Attribution

Amazon SP uses a **14-day click-through attribution window** by default for most metrics:

- `sales14d` / `purchases14d`: Sales and orders attributed within 14 days of a click
- `sales7d` / `purchases7d`: Sales and orders within 7 days (available in some report types)
- Conversion events can appear in the report up to 14 days after the last click

## Minimum Window Requirement

**Never draw ACoS or conversion conclusions from fewer than 14 days of data** unless explicitly acknowledged by the user. A 7-day window will under-count conversions that occur in days 8–14.

- For bid decisions: require ≥ 14 days of data
- For pause decisions: require ≥ 14 days of data with ≥ 20 clicks
- For harvest decisions: require ≥ 14 days of data

If the reporting window is shorter than 14 days:
> **Attribution Window Gate: BLOCKED** — reporting window is N days. Amazon 14-day attribution may not be fully captured. ACoS, CVR, and order counts may be understated. Extend the window to at least 14 days before making bid or pause decisions.

## Recency Lag

Data for the most recent 24–48 hours may not be fully attributed. When the report end date is today or yesterday:
> **Recency Note**: The most recent 1–2 days of data may not yet reflect all attributed conversions.

## Lifetime vs. Windowed Data

The `get_keyword_performance` tool returns performance for the requested date range only. There is no lifetime performance view available through the current MCP surface.

## Cross-Campaign Attribution

Amazon attributes a sale to the last ad click before purchase. If a customer clicks multiple ads, only the last campaign receives the attribution. The current MCP surface does not expose cross-campaign attribution overlap. This is a known limitation.

> **Cross-campaign attribution: UNSUPPORTED** — cannot determine if a campaign is losing attribution to another campaign in the same account.
