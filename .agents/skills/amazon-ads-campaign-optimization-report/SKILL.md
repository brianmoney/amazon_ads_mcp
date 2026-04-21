---
name: amazon-ads-campaign-optimization-report
description: 'Create Amazon Ads campaign optimization reports using the amazon-ads MCP tools. Use this skill whenever the user mentions campaign performance, keyword analysis, bid recommendations, spend or sales summaries, or any Amazon Ads reporting work — even if they do not say "optimization report" explicitly. Use when the user wants keyword performance analysis, campaign-level rollups, report-status polling, completed report retrieval, optimization CSV output, bid adjustment recommendations, pause candidates, or campaign/ad group/match-type summaries.'
argument-hint: 'Date range, campaign ids or profile context, and desired output path for the optimization report'
user-invocable: true
disable-model-invocation: false
---

# Amazon Ads Campaign Optimization Report

Generate a campaign optimization report from the `amazon-ads` MCP tool surface, even when Sponsored Products reports are asynchronous and may remain queued for a long time.

This skill packages the workflow used in this repository to:
- verify auth, region, and active profile state
- request Sponsored Products keyword performance reports
- poll report lifecycle status with `sp_report_status`
- recover completed reports when the original request timed out
- aggregate data to campaign, ad group, match type, and keyword levels
- produce operator-ready CSV outputs with action recommendations

## When to Use

- The user asks for a campaign optimization report
- The user wants keyword performance rolled up to campaign level
- A `get_keyword_performance` call times out while polling
- A report was already created and needs to be checked or retrieved later
- The user wants bid adjustment guidance, pause candidates, or spend/sales summaries
- The user wants a CSV written to the repository from Amazon Ads report data

## Inputs

- Reporting window: `start_date`, `end_date`
- Optional scope: `campaign_ids`, `ad_group_ids`, `keyword_ids`
- Optional output path for CSV or summary artifact
- Optional profile hint if no active profile is set

## Procedure

1. Validate basic MCP readiness.
   - Check OAuth state with `mcp_amazon-ads_check_oauth_status`.
   - If the access token is expired, refresh it with `mcp_amazon-ads_refresh_oauth_token`.
   - Check the active profile with `mcp_amazon-ads_get_active_profile`.
   - If no profile is active, find one with `mcp_amazon-ads_search_profiles` or `mcp_amazon-ads_summarize_profiles`, then set it with `mcp_amazon-ads_set_active_profile`.

2. Confirm the requested campaign scope before creating a report.
   - Use `mcp_amazon-ads_list_campaigns` when campaign IDs are unknown or need validation.
   - Prefer a narrow campaign scope when the user provides one, but remember that some report flows may still return broader data depending on the report already being resumed.

3. Request keyword performance data.
   - Call `mcp_amazon-ads_get_keyword_performance` with the requested date range and scope.
   - If the tool succeeds immediately, proceed to analysis.
   - If it returns a report timeout with a `report_id`, treat that report as in-flight instead of creating repeated duplicate requests. Extract and preserve the `report_id`, then go to step 4.

4. Handle asynchronous report states deliberately.
   - Poll the report with `mcp_amazon-ads_sp_report_status`, waiting **15–30 seconds between polls** to avoid burning API quota.
   - Interpret statuses as:
     - `COMPLETED`: ready to retrieve
     - `QUEUED` or `PENDING`: keep polling — this is normal Amazon queue latency, not a local outage
     - `FAILED` or `CANCELLED`: treat as terminal and report the failure clearly
   - Preserve the `report_id` in notes or output so the user can resume later if needed.

5. Retrieve completed report data.
   - Prefer using the MCP read tool if the runtime schema supports resume inputs.
   - If the MCP schema does not expose `resume_from_report_id`, fall back to:
     - call `mcp_amazon-ads_sp_report_status`
     - read the signed `download_url`
     - download and decompress the GZIP JSON payload using a terminal command or small script
   - Signed URLs expire; refresh them with another `sp_report_status` call if a download returns `403`.
   - The decompressed payload is a JSON array of objects. Each object represents one keyword row with fields like `campaignId`, `adGroupId`, `keywordText`, `matchType`, `impressions`, `clicks`, `cost`, `sales14d`, `purchases14d`, etc. Field names may vary slightly by report type — check the actual keys before aggregating.

6. Aggregate the report into decision-ready views.
   - Build campaign-level totals: impressions, clicks, spend, sales, orders, CTR, CPC, CVR, ACOS, ROAS.
   - Build ad-group rollups when helpful.
   - Build match-type summaries to isolate waste by `BROAD`, `PHRASE`, and `EXACT`.
   - Build keyword-level tables for:
     - top spend terms
     - top sales terms
     - wasted spend terms (`cost > 0` and `sales == 0`)
   - **Skip rows with zero impressions** — they carry no signal and inflate row counts.

   **Metric formulas** (use these exactly so outputs are consistent):
   ```
   CTR  = clicks / impressions
   CPC  = spend / clicks
   CVR  = orders / clicks
   ACOS = spend / sales          (undefined if sales == 0; mark as N/A)
   ROAS = sales / spend          (undefined if spend == 0; mark as N/A)
   ```

7. Produce optimization recommendations.

   **Bid adjustment formula** — use the target-ACOS method:
   ```
   suggested_bid = current_bid × (target_acos / actual_acos)
   suggested_bid_change_pct = ((suggested_bid / current_bid) - 1) × 100
   ```
   If the user does not provide a target ACOS, ask for it or default to 30% and state the assumption clearly in the output.

   **Pause candidate threshold** — flag a keyword as a pause candidate when:
   - clicks ≥ 20 **and** orders == 0 (meaningful traffic with no conversions), **or**
   - spend > 2× the average order value for the campaign and orders == 0
   State the threshold used in the output so the user can override it.

   **General guidance:**
   - Protect profitable or promising terms (low ACOS, positive CVR).
   - Recommend bid reductions for high-spend, zero-sales terms rather than pausing immediately if click volume is low.
   - Tie every recommendation back to campaign and ad group context.
   - If the report contains rows from multiple campaigns, state that explicitly in the output.

8. Write the requested artifact.
   - For CSV outputs, include rows for:
     - `CAMPAIGN`
     - `MATCH_TYPE`
     - `KEYWORD`
   - Suggested columns:
     - `report_date`
     - `scope`
     - `campaign_id`
     - `campaign_name`
     - `ad_group_id`
     - `ad_group_name`
     - `keyword`
     - `match_type`
     - `impressions`
     - `clicks`
     - `spend`
     - `sales`
     - `orders`
     - `ctr`
     - `cpc`
     - `cvr`
     - `acos`
     - `roas`
     - `recommended_action`
     - `suggested_bid_change_pct`
     - `priority`
     - `rationale`
   - Save the file at the exact path requested by the user.

## Decision Points

### If no active profile is set

- Search profiles and choose the correct advertiser before running reporting tools.

### If `get_keyword_performance` fails at report creation

- Do not assume auth is broken.
- Check whether the request shape has drifted or whether the runtime is using stale server code.
- Confirm container/runtime is serving the latest code if the repository was just changed.

### If `get_keyword_performance` times out while polling

- Extract and preserve the `report_id`.
- Use `sp_report_status` instead of creating repeated fresh reports.
- If the report remains `QUEUED`, treat the issue as upstream Amazon queue latency rather than an immediate local outage.

### If the MCP tool schema rejects `resume_from_report_id`

- Use `sp_report_status` to obtain a fresh signed download URL.
- Download the completed report directly and continue the analysis outside the MCP wrapper.

### If the completed report contains broader data than originally requested

- State that explicitly in the report.
- Filter or annotate the output so the user knows which rows match the requested campaign scope.

## Quality Checks

- Auth is valid or refreshed before report calls.
- Active profile is confirmed.
- Campaign IDs in the output are real and traceable via `list_campaigns`.
- Report status is checked before treating a timeout as terminal.
- Signed download URLs are refreshed if a download returns `403`.
- Campaign-level totals reconcile with the underlying keyword rows.
- Metric formulas match the definitions in step 6 (not computed ad hoc).
- Recommendations are tied to actual spend/sales signals, not just CTR.
- Pause candidates meet the stated threshold; threshold is disclosed in the output.
- The final artifact path exists and the file content matches the requested format.

## Output Expectations

The skill should produce one of these, depending on the user ask:
- a concise campaign performance summary
- a campaign optimization CSV in the repository
- a pause-candidate or bid-adjustment shortlist
- a stakeholder-ready summary tied back to campaign context

## Example Prompts

- `/amazon-ads-campaign-optimization-report Create a campaign optimization report for the last 7 days for campaign 432486167290577 and save it to ./reports/last-7-days.csv`
- `/amazon-ads-campaign-optimization-report The keyword performance report timed out. Poll the existing report and finish the analysis when it completes.`
- `/amazon-ads-campaign-optimization-report Build a CSV with campaign, match type, and keyword bid recommendations from the completed report.`
