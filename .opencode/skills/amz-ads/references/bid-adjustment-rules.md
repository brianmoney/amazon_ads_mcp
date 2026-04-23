# Bid Adjustment Rules Reference

Used by: `amz-bid-optimizer`, `amz-sp-audit`, `keyword-audit-agent`.

## Bid Adjustment Formula

```
suggested_bid = current_bid × (target_acos / actual_acos)
change_pct    = ((suggested_bid / current_bid) - 1) × 100
```

Use actual_acos as a decimal. If `actual_acos == 0` (no sales), do not use this formula — see the no-sales path below.

## Eligibility Gate

A keyword must pass ALL of the following before a bid adjustment is computed:

1. Clicks ≥ 10 (minimum click threshold per `quality-gates.md`)
2. Reporting window ≥ 14 days (attribution window compliance per `attribution.md`)
3. Keyword is in ENABLED state (not paused or archived)
4. ACoS is defined (sales > 0) — for no-sales path, see below

If a keyword fails any gate, classify as "insufficient data" — do not compute a bid change.

## No-Sales Path

When clicks ≥ 20 AND orders == 0:
- This is a pause candidate, not a bid-reduce candidate
- Do not apply the ACoS formula (ACoS is undefined when sales == 0)
- Flag for pause recommendation per `quality-gates.md`

When clicks < 20 AND orders == 0:
- Reduce bid by 20% as a conservative signal-gathering adjustment
- State explicitly: "Insufficient conversion data — small precautionary reduction"

## Bid Adjustment Caps

| Direction | Maximum Change |
|---|---|
| Increase | +50% per adjustment cycle |
| Decrease | −40% per adjustment cycle |

Do not suggest a single adjustment larger than these caps. If the formula suggests a larger change, cap it and note:
> "Capped at +50% — monitor for 14+ days before next adjustment."

## Bid Floors

| Scenario | Floor |
|---|---|
| Absolute minimum bid | $0.02 (Amazon minimum) |
| Brand defense keyword | Never reduce below $0.50 without explicit approval |
| Exact match proven converter (ACoS < 0.5× target) | Never reduce |

## Bid Ceilings

There is no hard ceiling. However, if the formula suggests a bid higher than the current campaign daily budget / estimated daily clicks, add a note:
> "Suggested bid may exhaust daily budget early — consider increasing budget or reducing bid target."

## Priority Sorting

Sort bid adjustment recommendations in this order:
1. Pause candidates (highest priority — stop waste first)
2. Bid-reduce (high ACoS, meaningful spend)
3. Bid-raise (profitable but under-spending)
4. Hold (no action needed)
5. Insufficient data (log only)

## Apply Constraint

All bid adjustments are approval-gated. The `adjust_keyword_bids` write tool must only be called after the user reviews and explicitly approves the adjustment set. Never auto-apply.

## Tools

- `get_keyword_performance`: provides keywordId, keywordText, matchType, bid, clicks, cost, sales14d, purchases14d
- `adjust_keyword_bids`: accepts `adjustments` list of `{ keyword_id, bid }` objects
