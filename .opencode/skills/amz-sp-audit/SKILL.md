---
name: amz-sp-audit
description: 'Run a full Sponsored Products campaign health audit using the live Amazon Ads MCP surface. Use this sub-skill when the user wants a comprehensive SP audit: keyword performance analysis, search-term waste review, campaign structure check, and a weighted health score with Quality Gate results. Invoked by amz-ads orchestrator or directly. Produces letter-graded health score, per-dimension subscores, and a complete recommendation set separated into read-only findings and approval-gated mutations.'
argument-hint: 'Campaign IDs, date range (start_date/end_date), and target ACoS'
user-invocable: true
disable-model-invocation: false
---

# amz-sp-audit — Sponsored Products Campaign Health Audit

Full SP audit sub-skill. Pulls keyword performance and search-term data, evaluates each campaign dimension against Quality Gates, and produces a scored health report with citations.

## MCP Tools Used

Read tools (always safe):
- `list_campaigns` — confirm campaign hierarchy
- `get_keyword_performance` — keyword metrics and derived stats
- `get_search_term_report` — search term traffic and waste
- `sp_report_status` — poll async report if timeout occurs

Write tools (approval-gated, never called automatically):
- `adjust_keyword_bids` — after bid recommendations approved
- `pause_keywords` — after pause list approved
- `negate_keywords` — after negative list approved
- `add_keywords` — after harvest list approved

## Procedure

1. Validate MCP readiness (OAuth, profile, region).
2. Call `list_campaigns` to confirm scope.
3. Call `get_keyword_performance` for the requested date range.
   - If timeout: extract `report_id`, poll with `sp_report_status`, resume with `resume_from_report_id`.
4. Call `get_search_term_report` for the same date range.
5. Compute metric-level calculations per `references/acos-math.md`.
6. Check attribution window compliance per `references/attribution.md`.
7. Apply minimum-volume gates per `references/quality-gates.md` before scoring.
8. Score each dimension per `references/scoring.md`.
9. Produce recommendations per `references/recommendation-contract.md`.
10. Surface all unsupported analyses explicitly (see `references/quality-gates.md` §Advisory and §Unsupported).

## Output

- Overall health score (0–100) and letter grade (A–F)
- Dimension subscores: keyword efficiency, search-term hygiene, bid calibration, structure
- Quality Gate summary: passed / blocked / advisory / unsupported
- Recommendation set: read-only findings + approval-gated mutations
- Unsupported analyses labeled with reason

## References

Load from `../amz-ads/references/` as needed:
`scoring.md`, `quality-gates.md`, `recommendation-contract.md`, `acos-math.md`,
`attribution.md`, `match-type-strategy.md`, `search-term-rules.md`, `bid-adjustment-rules.md`
