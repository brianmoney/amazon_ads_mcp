# Match-Type Strategy Reference

Used by: `amz-campaign-structure`, `amz-search-term-mining`, `amz-sp-audit`.

## Match Type Overview

| Match Type | Reach | Control | Primary Use |
|---|---|---|---|
| AUTO | Broadest | Lowest | Discovery — Amazon decides targeting |
| BROAD | High | Low-Medium | Discovery + new theme testing |
| PHRASE | Medium | Medium | Qualified traffic on known themes |
| EXACT | Narrow | Highest | Performance extraction on proven terms |

## Recommended Campaign Funnel

```
Auto Research campaign
  → discovers new search terms
  → converting terms promoted to Manual Discovery (BROAD/PHRASE)
  → top converters promoted to Exact Performance (EXACT)
  → waste terms negated at source campaign
```

### Why the Funnel Matters

- **Auto without negatives bleeds spend** to irrelevant queries
- **Exact without discovery stagnates** — you only bid on what you already know
- **Broad/phrase without exact protection** drives inconsistent performance as spend disperses

## Match-Type Decision Rules

### When to Add EXACT

- Search term has ≥ 3 clicks and ACoS ≤ target in the reporting window
- Search term is a proven converter in a broad/phrase ad group
- Search term is already exact-targeted: no action needed

### When to Use PHRASE

- Search term contains a core theme plus variable modifiers (size, color, style)
- Broad match is triggering irrelevant long-tail variants that dilute performance
- Advertiser wants to anchor on the core phrase while allowing modifier flexibility

### When to Use BROAD

- Early testing of a new keyword theme
- Low search volume niche where exact match would get zero impressions
- Exploratory campaigns alongside an auto campaign

### When to Pause or Remove a Match Type

- Exact keyword: clicks ≥ 20, orders == 0, spend > 2× average order value
- Broad/phrase keyword: ACoS > 2× target AND clicks ≥ 20

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Exact and broad targeting same term in same ad group | Cannibalization and mixed bid signaling | Separate into distinct ad groups or campaigns |
| Auto campaign with no negatives | Uncontrolled bleed to irrelevant queries | Add negative list from search-term waste analysis |
| Exact-only account | No discovery funnel, inventory stagnation | Add auto or broad discovery campaign |
| Broad targeting everything | Spend dispersed, low efficiency | Promote proven terms to exact; add negatives for waste |
