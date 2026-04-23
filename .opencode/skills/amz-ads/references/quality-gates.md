# Quality Gates Reference

Used by: all `amz-*` skills, audit agents, and the orchestrator.

Quality Gates are named checks that must be evaluated before drawing conclusions or surfacing recommendations. Every gate has an explicit state: **Passed**, **Blocked**, **Advisory**, or **Unsupported**.

- **Passed**: condition satisfied; proceed with full confidence
- **Blocked**: condition NOT satisfied; halt or heavily caveat the associated recommendation
- **Advisory**: partially satisfied; surface with limited-confidence note
- **Unsupported**: required data is not available from the current MCP surface; label explicitly

---

## Phase 1 Enforceable Gates

These gates can be checked using the current SP MCP tool surface.

### Gate: attribution_window_14d

**Check**: Reporting window is at least 14 days.

**Blocked condition**: `end_date - start_date < 14 days`

**Blocked behavior**:
> "Attribution Window Gate: BLOCKED — reporting window is N days. Amazon 14-day attribution may not be fully captured. ACoS, CVR, and order counts may be understated. Bid and pause decisions require at least 14 days of data."
- Do not make bid-adjust or pause recommendations when this gate is blocked
- You may still surface structural findings (campaign archetype, match-type coverage)

**Passed behavior**: proceed with full analysis

---

### Gate: min_clicks_threshold

**Check**: Keyword has ≥ 10 clicks in the reporting window before bid adjustment is computed.

**Blocked condition**: `clicks < 10`

**Blocked behavior**: Classify keyword as "insufficient data" — do not compute ACoS-based bid adjustment. Apply the small precautionary reduction path from `bid-adjustment-rules.md` only if clicks ≥ 1 and orders == 0.

**Passed behavior**: proceed with bid formula

---

### Gate: min_harvest_volume

**Check**: Search term has ≥ 3 clicks and ≥ 50 impressions before it is promoted as a harvest candidate.

**Blocked condition**: `clicks < 3 OR impressions < 50`

**Blocked behavior**: Classify as "monitor" — not enough signal to confidently promote as a keyword.

**Passed behavior**: eligible for harvest recommendation

---

### Gate: min_negate_volume

**Check**: Search term has ≥ 10 clicks before being recommended for negation.

**Blocked condition**: `clicks < 10 AND spend does not exceed 2× average order value`

**Blocked behavior**: Classify as "monitor" — do not recommend negation on low-click terms (may still convert).

**Exception**: If spend exceeds 2× average order value with zero orders, negate regardless of click count.

**Passed behavior**: eligible for negate recommendation

---

### Gate: approval_gated_mutation

**Check**: User has explicitly approved the change set before any write tool is called.

**Blocked condition**: No explicit user approval for this session.

**Blocked behavior**:
- All `apply-ready` recommendations remain in "pending approval" state
- Present the full recommendation set and ask for confirmation
- Do not call `adjust_keyword_bids`, `add_keywords`, `negate_keywords`, or `pause_keywords` until approved

**Passed behavior**: write tools may be called for the approved items only

---

### Gate: keyword_enabled_state

**Check**: Keyword is in ENABLED state before a bid adjustment is computed.

**Blocked condition**: Keyword state is PAUSED or ARCHIVED

**Blocked behavior**: Skip bid adjustment. Flag if a paused keyword has recent spend (data anomaly).

**Passed behavior**: proceed with bid adjustment eligibility check

---

### Gate: zero_impression_skip

**Check**: Row has impressions > 0 before any metric is computed.

**Blocked condition**: `impressions == 0`

**Blocked behavior**: Skip row entirely. Zero-impression rows carry no optimization signal.

**Passed behavior**: proceed with metric computation

---

## Advisory Gates

These gates can be partially evaluated but have limited confidence due to data constraints.

### Gate: budget_utilization_advisory

**State**: Always Advisory

**Check**: Estimated daily spend ÷ daily budget

**Limitation**: Daily spend is estimated from aggregate keyword spend / days in window. True pacing curves, hourly utilization, and impression-share-lost-to-budget data are not available.

**Behavior**: Surface as advisory with explicit confidence note. Never produce apply-ready budget recommendations.

---

### Gate: recency_lag_check

**State**: Advisory when end_date is within 2 days of today

**Check**: Report end date is more than 2 days ago

**Advisory condition**: `end_date >= today - 2`

**Behavior**:
> "Recency Note: Report end date is within the last 2 days. Conversion data for the most recent 1–2 days may not yet be fully attributed. ACoS and CVR may be understated for recent activity."
Surface as advisory note; do not block recommendations.

---

### Gate: auto_campaign_negative_coverage

**State**: Enforceable (checks if negatives exist) + Advisory (cannot verify completeness)

**Check**: Auto campaign has at least one campaign-level negative keyword.

**Blocked condition**: Auto campaign has zero negatives after 30+ days of run time.

**Behavior when blocked**: Flag as structural red flag. Recommend search-term audit to find waste candidates. Note that the MCP can confirm presence/absence of negatives but cannot evaluate whether the negative list is complete.

---

## Unsupported Gates

These analyses require data or tools not available in the current MCP surface. Always label them explicitly — never treat them as passed.

### Gate: placement_modifier_check

**State**: UNSUPPORTED

**What it would check**: Whether top-of-search vs. product page vs. rest-of-search placement performance warrants placement bid modifier changes.

**Why unsupported**: Placement-level metrics are not exposed by the current SP tool surface.

**Required statement**:
> "Placement modifier check: UNSUPPORTED — placement-level performance data is not available in the current MCP. Cannot recommend placement bid adjustments. See docs/amz-missing-information.md."

---

### Gate: organic_protection_check

**State**: UNSUPPORTED

**What it would check**: Whether the organic rank for primary keywords is strong enough that reducing ad bids would be safe.

**Why unsupported**: Organic rank data is not available through the current MCP surface.

**Required statement**:
> "Organic protection check: UNSUPPORTED — organic rank signals are not available in the current MCP. Cannot evaluate whether reducing ad spend would expose organic position risk."

---

### Gate: listing_quality_check

**State**: UNSUPPORTED

**What it would check**: Whether low CTR or CVR is caused by listing issues (images, title, bullets, pricing) rather than bid or targeting problems.

**Why unsupported**: Listing quality signals are not available in the current MCP surface.

**Required statement**:
> "Listing quality check: UNSUPPORTED — listing quality data is not available in the current MCP. Low CTR or CVR may be caused by listing issues that bid optimization cannot fix."

---

### Gate: category_benchmark_check

**State**: UNSUPPORTED

**What it would check**: Whether the account's ACoS and CTR are above or below category-level benchmarks.

**Why unsupported**: Category benchmark data is not available in the current MCP surface.

**Required statement**:
> "Category benchmark check: UNSUPPORTED — category-level ACoS and CTR benchmarks are not available in the current MCP. Cannot contextualize performance relative to category norms."

---

### Gate: tacos_check

**State**: UNSUPPORTED

**What it would check**: Total Advertising Cost of Sales (TACoS = ad spend / total revenue including organic).

**Why unsupported**: Total store revenue (organic + ad-attributed) is not available in the current MCP surface.

**Required statement**:
> "TACoS check: UNSUPPORTED — requires total store revenue. The current MCP only exposes ad-attributed revenue via get_keyword_performance."

---

### Gate: sponsored_brands_check

**State**: UNSUPPORTED (Phase 1)

**What it would check**: SB campaign performance, creative performance, and SB-specific metrics.

**Required statement**:
> "Sponsored Brands: UNSUPPORTED in phase 1 — SB tools are not available in the current MCP surface."

---

### Gate: sponsored_display_check

**State**: UNSUPPORTED (Phase 1)

**What it would check**: SD campaign performance, audience targeting efficiency, and SD-specific metrics.

**Required statement**:
> "Sponsored Display: UNSUPPORTED in phase 1 — SD tools are not available in the current MCP surface."

---

## Gate Evaluation Order

When running a full audit, evaluate gates in this order:

1. `attribution_window_14d` — if blocked, defer bid and pause decisions
2. `zero_impression_skip` — filter rows before any analysis
3. `keyword_enabled_state` — filter disabled keywords
4. `min_clicks_threshold` — classify keywords as eligible or insufficient
5. `min_harvest_volume` / `min_negate_volume` — classify search terms
6. `recency_lag_check` — add advisory note if applicable
7. `auto_campaign_negative_coverage` — structural check
8. `budget_utilization_advisory` — always advisory
9. All Unsupported gates — always surface, never skip
10. `approval_gated_mutation` — last gate before any write action
