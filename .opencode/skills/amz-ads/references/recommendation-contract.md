# Recommendation Output Contract

Used by: all `amz-*` skills, audit agents, and the orchestrator.

Every recommendation in this skill family must follow this format. No recommendation may be surfaced without the required citation fields.

## Required Fields for Every Recommendation

```
recommendation:
  id: <unique within this output, e.g. "REC-001">
  type: <bid-adjust | bid-raise | pause | negate | add-keyword | structure | advisory | unsupported-gap>
  status: <read-only | apply-ready | advisory | unsupported>
  priority: <critical | high | medium | low>

  subject:
    campaign_id: <id>
    campaign_name: <name>
    ad_group_id: <id or null>
    ad_group_name: <name or null>
    keyword_id: <id or null>
    keyword_text: <text or null>
    match_type: <EXACT | BROAD | PHRASE | AUTO | null>

  finding: >
    One sentence describing what the data shows.

  rationale: >
    One to three sentences explaining why this is a problem or opportunity,
    citing specific metric values.

  action: >
    The specific change being recommended (e.g., "Reduce bid from $1.20 to $0.72").
    For advisory or unsupported, describe what would be done if data were available.

  source_tools:
    - <tool name used to source the data, e.g. get_keyword_performance>
    - <additional tools if multiple sources used>

  data_window:
    start_date: <YYYY-MM-DD>
    end_date: <YYYY-MM-DD>

  gates_passed:
    - <gate name>: <brief note>

  gates_blocked:
    - <gate name>: <reason blocked>

  gates_unsupported:
    - <gate name>: <what data is missing>

  metrics:
    <key metrics that support the finding, e.g.>
    clicks: 47
    orders: 0
    spend: "$18.43"
    acos: "N/A"
    current_bid: "$1.20"
    suggested_bid: "$0.72"
    change_pct: "-40%"

  apply_tool: <tool name to call, or null if read-only/advisory>
  apply_args: <arg shape for the write tool, or null>
```

## Status Definitions

| Status | Meaning |
|---|---|
| `read-only` | Finding from data analysis. No write action available or recommended yet. |
| `apply-ready` | Write tool identified and args prepared. Requires user approval before calling. |
| `advisory` | Finding has limited confidence due to missing data or attribution constraints. Not apply-ready. |
| `unsupported` | Analysis requires data or tools not available in the current MCP surface. Surface explicitly, do not skip. |

## Apply-Ready Constraint

No recommendation with `status: apply-ready` may have its `apply_tool` called without explicit user approval. The output section must clearly present the full apply-ready list and ask for confirmation before executing any write tools.

## Output Section Structure

Every recommendation output must include these top-level sections in order:

### 1. Health Score Summary

```
Overall Health Score: <N>/100  Grade: <letter>
  Keyword Efficiency:     <N>/25
  Search-Term Hygiene:    <N>/25
  Bid Calibration:        <N>/25
  Campaign Structure:     <N>/25

Sources: list_campaigns, get_keyword_performance, get_search_term_report
Window: YYYY-MM-DD to YYYY-MM-DD
```

### 2. Quality Gate Summary

```
Gates Passed:     <N>
Gates Blocked:    <N>
Gates Advisory:   <N>
Gates Unsupported: <N>

Blocked Gates:
  - attribution_window_14d: window is only 7 days — conversion data may be incomplete
  ...

Unsupported Gates:
  - placement_modifier_check: placement report not available in current MCP
  ...
```

### 3. Read-Only Findings

List all `status: read-only` recommendations. No action required from user to acknowledge these.

### 4. Apply-Ready Recommendations

List all `status: apply-ready` recommendations with full apply args visible. Pause for user approval before calling any write tools.

```
The following N changes are ready to apply. Please review and confirm.

[Y] REC-003 — Pause keyword "generic widget" (EXACT, ad group 12345)
    Clicks: 34  Orders: 0  Spend: $22.10
    Apply: pause_keywords keyword_ids=["9876543"]

[Y] REC-007 — Reduce bid "blue widget" BROAD from $1.40 → $0.90
    ACoS: 48%  Target: 30%  Change: -36%
    Apply: adjust_keyword_bids [{ keyword_id: "1234567", bid: 0.90 }]

Confirm to apply all, or specify which to skip:
```

### 5. Advisory Notes

List all `status: advisory` items with confidence note attached.

### 6. Unsupported Analyses

List all analyses that could not be performed due to missing MCP surface. Do not omit this section even if empty.

```
The following analyses are NOT supported by the current MCP surface:

- TACoS analysis: requires total store revenue — not available
- Placement modifier recommendations: requires placement report — not available
- Impression share: not available in current MCP
- Sponsored Brands and Sponsored Display: not covered in phase 1
```
