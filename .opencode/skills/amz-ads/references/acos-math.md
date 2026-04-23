# ACoS / TACoS Math Reference

Used by: all SP sub-skills and audit agents.

## Definitions

```
ACoS  = Ad Spend / Ad Revenue × 100             (Advertising Cost of Sales)
TACoS = Ad Spend / Total Revenue × 100          (Total Advertising Cost of Sales)
ROAS  = Ad Revenue / Ad Spend                   (Return on Ad Spend)
CTR   = Clicks / Impressions
CPC   = Ad Spend / Clicks
CVR   = Orders / Clicks                         (Conversion Rate)
```

- **ACoS** measures ad efficiency relative to ad-attributed sales only.
- **TACoS** measures ad spend relative to total store revenue (organic + ad). Lower TACoS over time signals healthy organic growth. TACoS is **not computable** from the current MCP surface — it requires total store revenue, which is not exposed. Always label TACoS as unsupported.
- **ROAS** is the inverse of ACoS expressed as a ratio. ROAS = 1 / ACoS (when both use decimal form).

## Special Cases

| Condition | Handling |
|---|---|
| `sales == 0` | ACoS = undefined. Mark as N/A. Do not compute. |
| `spend == 0` | ROAS = undefined, CPC = undefined. Mark as N/A. |
| `clicks == 0` | CVR = undefined. CTR may still be computed if impressions > 0. |
| `impressions == 0` | Skip the row entirely. Zero-impression rows carry no signal. |

## Target ACoS

If the user does not provide a target ACoS:
- Default to **30%** (0.30 as decimal).
- State the assumption explicitly in every section that uses it.
- Prompt the user for their actual target before finalizing recommendations.

## ACoS Thresholds for Bid Action

| ACoS relative to target | Action |
|---|---|
| < 0.7 × target | Bid-raise candidate (under-bidding profitable term) |
| 0.7–1.5 × target | Hold — within acceptable range |
| 1.5–2.0 × target | Bid-reduce candidate |
| > 2.0 × target | Strong bid-reduce or pause candidate |

## ROAS Minimum

A keyword with ROAS < 0.5 and sufficient click volume (≥ 20 clicks) should be flagged as a strong bid-reduce candidate regardless of order count.

## Attribution Windows

See `references/attribution.md` for how attribution windows affect ACoS reliability.

## TACoS Is Unsupported

TACoS requires total store revenue. The current MCP surface does not expose organic revenue or total revenue data. Always surface this explicitly:

> **TACoS: UNSUPPORTED** — requires total store revenue. Current MCP surface only exposes ad-attributed revenue via `get_keyword_performance`. Use Amazon Seller Central or the Reporting API directly for TACoS analysis.
