---
name: amz-campaign-structure
description: 'Review campaign structure using live campaign-discovery tools and recommend reorganization patterns without inventing unsupported data.'
argument-hint: 'Current campaign scope, structural pain points, and whether the request is Sponsored Products or Sponsored Display'
user-invocable: true
disable-model-invocation: false
---

# amz-campaign-structure

Use live campaign-discovery tools to ground structure recommendations.

## Procedure

1. Read `../amz-ads/references/mcp-tool-surface.md`.
2. Validate auth, active profile, and region.
3. Use `list_campaigns` for Sponsored Products structure discovery.
4. Use `list_sd_campaigns` when the request is limited to Sponsored Display campaign discovery.
5. If the request needs unsupported surfaces such as Sponsored Brands structure or Sponsored Display write planning, say so explicitly.
