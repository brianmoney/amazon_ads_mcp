---
name: amz-ads
description: 'Orchestrate Amazon Ads workflows against the live MCP surface. Use for Amazon Ads audits, campaign discovery, search-term analysis, bidding questions, pacing analysis, or supported Sponsored Display reads.'
argument-hint: 'User goal, reporting window, campaign scope, and any profile or region context'
user-invocable: true
disable-model-invocation: false
---

# amz-ads

Route Amazon Ads requests to the smallest supported workflow without inventing tools or data.

## First Step

- Read `references/mcp-tool-surface.md` before choosing a workflow.
- Confirm auth, active profile, and region with the live MCP utility tools before using Amazon Ads reads or writes.

## Routing

- Broad Sponsored Products audit: use `amz-sp-audit`.
- Search-term harvesting or negation analysis: use `amz-search-term-mining`.
- Bid recommendations: use `amz-bid-optimizer`.
- Budget pacing analysis: use `amz-budget-pacing`.
- Campaign structure recommendations: use `amz-campaign-structure`.
- Sponsored Display campaign discovery: use `list_sd_campaigns`.
- Sponsored Display targeting-group performance: use `get_sd_performance`.
- Sponsored Display async status checks: use `sd_report_status` for known in-flight SD report IDs.

## Sponsored Display Guardrails

- Supported Sponsored Display reads are limited to `list_sd_campaigns`, `get_sd_performance`, and `sd_report_status`.
- For long-running Sponsored Display reports, request once with `get_sd_performance`, preserve the returned `report_id`, poll with `sd_report_status`, and resume with `get_sd_performance(resume_from_report_id=...)` when the report is `COMPLETED`.
- Do not create duplicate Sponsored Display reports when an existing `report_id` is still `QUEUED` or `PROCESSING`.
- If the user asks for a mixed request, complete the supported Sponsored Display portion with the real tool names above.
- State any unsupported remainder explicitly. Do not treat the full Sponsored Display surface as unavailable when campaign discovery or targeting-group performance is enough to help.
- Keep these surfaces unsupported unless a real MCP tool exists: Sponsored Display writes, audience mutations, creative automation, category benchmarks, organic rank, listing quality, and all Sponsored Brands workflows.

## Mutation Guardrail

- Keep workflows read-first by default.
- Do not call write tools until the user approves the proposed change set.
