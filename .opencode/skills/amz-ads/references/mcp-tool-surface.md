# Amazon Ads MCP Tool Surface

Use only the real tool names published by this repository.

## Utility Tools

- `check_oauth_status`
- `refresh_oauth_token`
- `get_active_profile`
- `set_active_profile`
- `search_profiles`
- `summarize_profiles`
- `get_region`
- `set_region`

## Sponsored Products Reads

- `list_campaigns`
- `get_keyword_performance`
- `get_campaign_budget_history`
- `get_impression_share_report`
- `get_placement_report`
- `get_search_term_report`
- `sp_report_status`

## Sponsored Products Writes

- `adjust_keyword_bids`
- `add_keywords`
- `negate_keywords`
- `pause_keywords`
- `update_campaign_budget`

## Sponsored Display Reads

- `list_sd_campaigns`: campaign discovery with lightweight targeting-group context when available
- `get_sd_performance`: targeting-group performance reporting with resumable report retrieval through `resume_from_report_id`
- `sd_report_status`: inspect the lifecycle state of an existing Sponsored Display async report by `report_id`

## Supported Workflow Boundaries

- Sponsored Products audits and reporting are supported with the tool names above.
- Sponsored Display support is limited to campaign discovery, async report status checks, and targeting-group performance analysis.
- For long-lived Sponsored Display reports, use `get_sd_performance` to request the report, preserve the returned `report_id`, poll `sd_report_status` at bounded intervals, and resume with `get_sd_performance(resume_from_report_id=...)` after completion.
- When an SD request contains supported and unsupported parts, complete the supported part and call out the unsupported remainder explicitly.

## Unsupported Surfaces

- Sponsored Display writes or automated audience changes
- Sponsored Display creative automation
- Sponsored Brands reads or writes
- Organic rank and TACoS grounded in organic sales data
- Listing-quality diagnostics
- Category benchmarks
- Portfolio budget management

If a workflow depends on an unsupported surface, say so plainly and do not invent substitute tool names.
