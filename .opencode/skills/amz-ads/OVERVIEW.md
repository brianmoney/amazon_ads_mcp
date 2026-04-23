# Amazon Ads Skill Family — Architecture Overview

This directory contains the `amz-ads` orchestrator and its supporting sub-skills, references, and agents for Amazon Ads optimization.

## Skill Inventory

### Orchestrator

| Skill | Description |
|---|---|
| `amz-ads` | Top-level orchestrator. Dispatches to sub-skills or parallel agents. Handles auth, profile, and scope validation. |

### Sub-Skills (Invoke Directly or via Orchestrator)

| Skill | Purpose |
|---|---|
| `amz-sp-audit` | Full SP campaign health audit with scoring and Quality Gates |
| `amz-search-term-mining` | Search-term waste identification and keyword harvest workflow |
| `amz-bid-optimizer` | Keyword bid adjustment using target-ACoS formula |
| `amz-budget-pacing` | Budget utilization analysis (advisory — limited MCP surface) |
| `amz-campaign-structure` | Campaign hierarchy and archetype alignment review |

### Existing Adjacent Skill (Not Part of This Family)

| Skill | Description |
|---|---|
| `amazon-ads-campaign-optimization-report` | Report-focused workflow: CSV artifacts, async report polling, operator-ready output. Unchanged by this family. |

## Architecture Model

```
User or Agent
    │
    ▼
amz-ads (orchestrator)
    │
    ├── Validate MCP readiness (OAuth, profile, region)
    ├── Load campaign scope (list_campaigns)
    │
    ├── Sequential path: invoke sub-skill
    │       amz-sp-audit / amz-bid-optimizer / amz-search-term-mining
    │       amz-budget-pacing / amz-campaign-structure
    │
    └── Parallel path: launch agents concurrently, merge results
            keyword-audit-agent + search-term-audit-agent
            + structure-audit-agent + budget-audit-agent
    │
    ▼
References loaded on demand:
    scoring.md, quality-gates.md, recommendation-contract.md
    acos-math.md, attribution.md, match-type-strategy.md
    search-term-rules.md, bid-adjustment-rules.md
    mcp-tool-surface.md, archetypes/

    │
    ▼
Output:
    Health score (0–100, A–F)
    Quality Gate results (passed / blocked / advisory / unsupported)
    Read-only findings
    Apply-ready recommendations (approval-gated)
    Unsupported analyses labeled
```

## Quality Gate Model

Gates are evaluated before any recommendation is surfaced. See `references/quality-gates.md` for the full list.

| Gate Category | Examples |
|---|---|
| **Enforceable** | Attribution window ≥ 14 days, min click threshold, approval before write tools |
| **Advisory** | Budget utilization (no pacing history), recency lag (recent data incomplete) |
| **Unsupported** | Placement metrics, organic rank, listing quality, TACoS, SB/SD |

Unsupported gates are **always surfaced explicitly** in output — never silently skipped.

## MCP Write Tool Policy

All write tools are approval-gated. The sequence is:

1. Run read analysis (always safe)
2. Produce apply-ready recommendation set
3. Present to user for review
4. Call write tools only for approved items

Write tools: `adjust_keyword_bids`, `add_keywords`, `negate_keywords`, `pause_keywords`

## Phase 1 Scope

Phase 1 covers **Sponsored Products only**. The following are explicitly out of scope until new MCP capabilities are added:

- Sponsored Brands (SB)
- Sponsored Display (SD)
- Placement modifier optimization
- Organic rank / TACoS analysis
- Listing quality diagnosis
- Budget pacing history (advisory workaround in place)

See `docs/amz-missing-information.md` for the expansion roadmap.

## Reference File Map

```
references/
├── scoring.md                — 0–100 health score, letter grades, dimension weights
├── quality-gates.md          — all gate definitions (enforceable, advisory, unsupported)
├── recommendation-contract.md — output citation format and required fields
├── acos-math.md              — ACoS/TACoS/ROAS formulas and thresholds
├── attribution.md            — Amazon 14-day attribution window rules
├── match-type-strategy.md    — match-type decision framework and anti-patterns
├── search-term-rules.md      — harvest and waste classification rules
├── bid-adjustment-rules.md   — bid formula, caps, floors, eligibility
├── mcp-tool-surface.md       — live tool names, supported workflows, unsupported areas
└── archetypes/
    ├── auto-research.md
    ├── manual-discovery.md
    ├── exact-performance.md
    ├── product-targeting.md
    └── brand-defense.md
```
