---
name: amz-ads
description: 'Orchestrate Amazon Ads optimization workflows for Sponsored Products campaigns. Use this skill when the user wants a full campaign health audit, bid optimization, search-term harvesting, budget analysis, or campaign structure review backed by the live MCP tool surface. Delegates to focused sub-skills (amz-sp-audit, amz-search-term-mining, amz-bid-optimizer, amz-budget-pacing, amz-campaign-structure) and optional parallel audit agents. Produces weighted health scores, Quality Gate results, and approval-gated recommendations. Phase 1 covers Sponsored Products only; unsupported surfaces (SB, SD, placement, organic, listing quality) are labeled explicitly.'
argument-hint: 'Scope of analysis: campaign IDs, date range, target ACoS, and desired workflow (audit / bid-optimize / search-term-harvest / structure-review)'
user-invocable: true
disable-model-invocation: false
---

# amz-ads — Amazon Ads Optimization Orchestrator

Phase-1 orchestrator for the Amazon Ads skill family. Dispatches to focused sub-skills, loads references on demand, and coordinates optional parallel audit agents against the live Sponsored Products MCP surface.

## Architecture

```
amz-ads (orchestrator)
├── amz-sp-audit          — full SP campaign health audit
├── amz-search-term-mining — search term waste + harvest workflow
├── amz-bid-optimizer     — keyword bid adjustment workflow
├── amz-budget-pacing     — budget utilization analysis (advisory)
└── amz-campaign-structure — campaign hierarchy review

references/
├── scoring.md            — weighted health score + Quality Gate model
├── quality-gates.md      — enforceable, advisory, and unsupported gates
├── recommendation-contract.md — output citation format
├── acos-math.md          — ACoS / TACoS formulas and thresholds
├── attribution.md        — Amazon attribution window rules
├── match-type-strategy.md — match-type decision framework
├── search-term-rules.md  — search-term waste and harvest rules
├── bid-adjustment-rules.md — bid adjustment formulas and constraints
├── mcp-tool-surface.md   — live tool names and unsupported areas
└── archetypes/
    ├── auto-research.md
    ├── manual-discovery.md
    ├── exact-performance.md
    ├── product-targeting.md
    └── brand-defense.md

agents/
├── keyword-audit-agent.md
├── search-term-audit-agent.md
├── structure-audit-agent.md
└── budget-audit-agent.md
```

## When to Use

- The user asks for a campaign audit, health score, or optimization review
- The user wants bid recommendations, search-term waste analysis, or keyword harvesting
- The user wants a structured recommendation set ready for approval and apply
- The user wants to understand campaign structure issues or archetype mismatches

## Supported Workflows (Phase 1)

| Workflow | Sub-skill | Key MCP Tools |
|---|---|---|
| Full SP audit | amz-sp-audit | `list_campaigns`, `get_keyword_performance`, `get_search_term_report` |
| Search-term harvesting | amz-search-term-mining | `get_search_term_report`, `add_keywords`, `negate_keywords` |
| Bid optimization | amz-bid-optimizer | `get_keyword_performance`, `adjust_keyword_bids` |
| Budget pacing | amz-budget-pacing | `list_campaigns` (advisory only — no budget history available) |
| Structure review | amz-campaign-structure | `list_campaigns`, `get_keyword_performance` |

## Unsupported in Phase 1

These analyses are **not supported** by the current MCP surface. Always surface them explicitly:

- Sponsored Brands (SB) and Sponsored Display (SD) performance
- Placement-level metrics and placement modifier recommendations
- Organic rank protection signals
- Listing quality diagnosis
- Category-level benchmark comparisons
- Day-by-day budget pacing history

See `references/mcp-tool-surface.md` for the full gap list and `docs/amz-missing-information.md` for the expansion roadmap.

## Inputs

- `campaign_ids`: list of SP campaign IDs (optional; defaults to active profile scope)
- `start_date`, `end_date`: reporting window (ISO 8601)
- `target_acos`: advertiser target ACoS as a decimal (e.g., 0.30 = 30%)
- `workflow`: `audit` | `bid-optimize` | `search-term-harvest` | `structure-review`
- `parallel_agents`: `true` to run keyword, search-term, structure, and budget agents in parallel (default: false)

## Procedure

### 1. Validate MCP readiness

```
check_oauth_status → refresh_oauth_token (if expired)
get_active_profile → set_active_profile (if none)
get_region → set_region (if needed)
```

### 2. Load campaign scope

Call `list_campaigns` to confirm campaign IDs, states, and ad group structure.

### 3. Dispatch to sub-skill or parallel agents

For `audit` workflow, either:
- Sequential: invoke `amz-sp-audit`
- Parallel: launch `agents/keyword-audit-agent.md`, `agents/search-term-audit-agent.md`, `agents/structure-audit-agent.md`, and `agents/budget-audit-agent.md` concurrently; merge results in the orchestrator

For targeted workflows:
- `bid-optimize` → `amz-bid-optimizer`
- `search-term-harvest` → `amz-search-term-mining`
- `structure-review` → `amz-campaign-structure`

### 4. Load references on demand

Pull in relevant reference files as needed:
- Scoring formula: `references/scoring.md`
- Gate definitions: `references/quality-gates.md`
- Output format: `references/recommendation-contract.md`
- Amazon math: `references/acos-math.md`, `references/attribution.md`
- Strategy: `references/match-type-strategy.md`, `references/search-term-rules.md`, `references/bid-adjustment-rules.md`
- Campaign patterns: `references/archetypes/`

### 5. Compute health score and Quality Gate results

Follow `references/scoring.md` to produce:
- Overall health score (0–100)
- Letter grade (A–F)
- Per-dimension subscores
- Passed, blocked, and unsupported gate list

### 6. Produce recommendations

Follow `references/recommendation-contract.md`:
- Each recommendation cites the source MCP read tools
- Passed gates are listed
- Blocked gates are listed with reason
- Read-only findings are separated from apply-ready mutations
- Unsupported analyses are labeled, not omitted

### 7. Obtain approval before any write tools

Write tools (`adjust_keyword_bids`, `add_keywords`, `negate_keywords`, `pause_keywords`) must only be called after the user reviews and approves the recommendation set.

## Quality Checks

- OAuth and profile are valid before any tool call
- Campaign IDs in recommendations are confirmed by `list_campaigns`
- Health score dimensions cite the specific tools that sourced each metric
- All blocked or unsupported gates are surfaced in output, not silently skipped
- Write steps are clearly marked apply-ready and gated on user approval
- Attribution window requirements are honored (see `references/attribution.md`)
- Minimum click/impression thresholds are applied before scoring (see `references/quality-gates.md`)
