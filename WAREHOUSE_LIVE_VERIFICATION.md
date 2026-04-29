# Warehouse Live Verification Runbook

Use this runbook to verify one deterministic live warehouse-ingestion
rehearsal before you trust cached reads for a profile and region.

## Scope

- One profile
- One region
- One worker cycle
- Scheduler disabled
- Warehouse validation enabled

This runbook intentionally uses
`uv run python -m amazon_ads_mcp.warehouse.worker_entrypoint --run-once`
with `WAREHOUSE_SCHEDULER_ENABLED=false` so every persisted row can be
attributed to one bounded rehearsal.

## Prerequisites

- A real Amazon Ads identity that can see the target profile in the target
  region
- A Postgres warehouse database reachable through
  `WAREHOUSE_DATABASE_DSN`
- Auth environment configured the same way you would run the live MCP server
  (`AUTH_METHOD=direct` or `AUTH_METHOD=openbridge` plus the matching
  credentials)
- A profile with known recent Sponsored Products and portfolio activity so the
  rehearsal produces meaningful evidence

If your chosen profile does not have recent activity, the worker may still run
successfully, but zero-row fact tables are not useful acceptance evidence.

## Recommended Environment

Set one profile, one region, validation on, and the default lagged report
window:

```bash
export WAREHOUSE_WORKER_ENABLED=true
export WAREHOUSE_DATABASE_DSN="postgresql+psycopg://amazon_ads:amazon_ads@localhost:5433/amazon_ads"
export WAREHOUSE_PROFILE_IDS="1234567890"
export WAREHOUSE_REGIONS="na"
export WAREHOUSE_SCHEDULER_ENABLED=false
export WAREHOUSE_VALIDATION_ENABLED=true
export WAREHOUSE_REPORT_WINDOW_DAYS=1
export WAREHOUSE_REPORT_LAG_DAYS=1
```

The default report window logic is:

- `window_end = current_date - WAREHOUSE_REPORT_LAG_DAYS`
- `window_start = window_end - (WAREHOUSE_REPORT_WINDOW_DAYS - 1)`

With the defaults above, the worker should request yesterday only.

## Run The Rehearsal

Run one bounded cycle:

```bash
uv run python -m amazon_ads_mcp.warehouse.worker_entrypoint --run-once
```

Record the profile, region, and the UTC timestamp when the run started. Use the
same values in the SQL checks below.

For the SQL snippets below, replace the example `profile_id`, `region`,
`run_started_at`, `window_start`, and `window_end` values with the values from
your rehearsal before you run them.

## Post-Run Evidence Checklist

### 1. Confirm expected `ingestion_job` rows

The rehearsal should leave one deterministic `ingestion_job` row per in-scope
surface:

- `ads_profile`
- `list_portfolios`
- `list_campaigns`
- `sp_keyword`
- `get_keyword_performance`
- `get_search_term_report`
- `get_campaign_budget_history`
- `get_placement_report`
- `get_impression_share_report`
- `get_portfolio_budget_usage`
- `warehouse_validation`

Run:

```sql
WITH params AS (
  SELECT
    '1234567890'::text AS profile_id,
    'na'::text AS region,
    TIMESTAMPTZ '2026-04-28T00:00:00Z' AS run_started_at
)
SELECT
  surface_name,
  job_type,
  status,
  window_start,
  window_end,
  completed_at,
  last_error_text
FROM ingestion_job
WHERE profile_id = (SELECT profile_id FROM params)
  AND region = (SELECT region FROM params)
  AND started_at >= (SELECT run_started_at FROM params)
ORDER BY started_at DESC, surface_name;
```

Pass criteria:

- Each surface above appears exactly once for the rehearsal scope.
- `status = 'completed'` for every ingestion surface.
- `warehouse_validation` is also `completed`.
- `last_error_text` is empty for the passing rehearsal.

Fail the rehearsal if any required surface is missing, duplicated for the same
window, or marked `failed`.

### 2. Confirm `report_run` evidence for report-backed surfaces

The five report-backed surfaces should each persist a durable report run:

- `get_keyword_performance`
- `get_search_term_report`
- `get_campaign_budget_history`
- `get_placement_report`
- `get_impression_share_report`

Run:

```sql
WITH params AS (
  SELECT
    '1234567890'::text AS profile_id,
    'na'::text AS region,
    TIMESTAMPTZ '2026-04-28T00:00:00Z' AS run_started_at,
    DATE '2026-04-27' AS window_start,
    DATE '2026-04-27' AS window_end
)
SELECT DISTINCT ON (rr.surface_name)
  rr.surface_name,
  rr.report_type_id,
  rr.status,
  rr.raw_status,
  rr.row_count,
  rr.amazon_report_id,
  rr.window_start,
  rr.window_end,
  rr.error_text,
  rr.requested_at,
  rr.last_polled_at,
  rr.completed_at,
  rr.retrieved_at
FROM report_run AS rr
WHERE rr.profile_id = (SELECT profile_id FROM params)
  AND rr.window_start = (SELECT window_start FROM params)
  AND rr.window_end = (SELECT window_end FROM params)
  AND rr.surface_name IN (
    'get_keyword_performance',
    'get_search_term_report',
    'get_campaign_budget_history',
    'get_placement_report',
    'get_impression_share_report'
  )
ORDER BY
  rr.surface_name,
  rr.requested_at DESC,
  rr.last_polled_at DESC NULLS LAST,
  rr.completed_at DESC NULLS LAST;
```

Pass criteria:

- One scope-matching `report_run` is present for each report-backed surface.
- The matching row may have been created in this rehearsal or resumed from a
  prior attempt for the same profile and window.
- `status = 'completed'` for each inspected row.
- `amazon_report_id` is populated.
- `window_start` and `window_end` match the expected lagged window.

Fail the rehearsal if any inspected `report_run` has a non-`completed` status
such as `queued`, `processing`, `failed`, or `cancelled`, or if it points at
the wrong window.

### 3. Confirm phase 1 warehouse tables were populated

`list_campaigns` loads both `sp_campaign` and `sp_ad_group`, so both tables are
part of the evidence set.

Run:

```sql
WITH params AS (
  SELECT
    '1234567890'::text AS profile_id,
    DATE '2026-04-27' AS window_start,
    DATE '2026-04-27' AS window_end
)
SELECT 'ads_profile' AS table_name, count(*) AS row_count
FROM ads_profile
WHERE profile_id = (SELECT profile_id FROM params)
UNION ALL
SELECT 'portfolio', count(*)
FROM portfolio
WHERE profile_id = (SELECT profile_id FROM params)
UNION ALL
SELECT 'sp_campaign', count(*)
FROM sp_campaign
WHERE profile_id = (SELECT profile_id FROM params)
UNION ALL
SELECT 'sp_ad_group', count(*)
FROM sp_ad_group
WHERE profile_id = (SELECT profile_id FROM params)
UNION ALL
SELECT 'sp_keyword', count(*)
FROM sp_keyword
WHERE profile_id = (SELECT profile_id FROM params)
UNION ALL
SELECT 'sp_keyword_performance_fact', count(*)
FROM sp_keyword_performance_fact
WHERE profile_id = (SELECT profile_id FROM params)
  AND window_start = (SELECT window_start FROM params)
  AND window_end = (SELECT window_end FROM params)
UNION ALL
SELECT 'sp_search_term_fact', count(*)
FROM sp_search_term_fact
WHERE profile_id = (SELECT profile_id FROM params)
  AND window_start = (SELECT window_start FROM params)
  AND window_end = (SELECT window_end FROM params)
UNION ALL
SELECT 'sp_campaign_budget_history_fact', count(*)
FROM sp_campaign_budget_history_fact
WHERE profile_id = (SELECT profile_id FROM params)
  AND budget_date BETWEEN (SELECT window_start FROM params)
    AND (SELECT window_end FROM params)
UNION ALL
SELECT 'sp_placement_fact', count(*)
FROM sp_placement_fact
WHERE profile_id = (SELECT profile_id FROM params)
  AND window_start = (SELECT window_start FROM params)
  AND window_end = (SELECT window_end FROM params)
UNION ALL
SELECT 'sp_impression_share_fact', count(*)
FROM sp_impression_share_fact
WHERE profile_id = (SELECT profile_id FROM params)
  AND window_start = (SELECT window_start FROM params)
  AND window_end = (SELECT window_end FROM params)
UNION ALL
SELECT 'portfolio_budget_usage_snapshot', count(*)
FROM portfolio_budget_usage_snapshot
WHERE profile_id = (SELECT profile_id FROM params);
```

Pass criteria:

- Dimension tables contain rows for the rehearsal profile.
- Report-backed fact tables contain rows for the rehearsal window when the
  chosen profile has recent activity.
- `portfolio_budget_usage_snapshot` contains rows for visible portfolio ids.

For `sp_impression_share_fact` and `portfolio_budget_usage_snapshot`, a row can
still be valid evidence when Amazon marks the surface unavailable. In that case,
accept the row if the diagnostic fields are populated and later validation says
the live and warehouse availability states match.

### 4. Confirm `freshness_watermark` rows

Run:

```sql
WITH params AS (
  SELECT
    '1234567890'::text AS profile_id,
    'na'::text AS region
)
SELECT
  surface_name,
  last_successful_window_end,
  last_snapshot_at,
  last_attempted_at,
  last_status
FROM freshness_watermark
WHERE profile_id = (SELECT profile_id FROM params)
  AND region = (SELECT region FROM params)
ORDER BY surface_name;
```

Pass criteria:

- Each report-backed surface has `last_successful_window_end` set to the
  expected lagged window end.
- Snapshot and dimension surfaces have a recent `last_snapshot_at`.
- `warehouse_validation` has `last_status = 'completed'`.

Fail the rehearsal if a report-backed watermark advances to today under the
default lagged configuration, or if a validation watermark records `mismatch`
or `failed`.

## Pass/Fail Checks

### Default lagged report window

For the baseline rehearsal, leave `WAREHOUSE_REPORT_WINDOW_DAYS=1` and
`WAREHOUSE_REPORT_LAG_DAYS=1`.

Pass if:

- Every report-backed `ingestion_job.window_start` and `window_end` points at
  yesterday.
- Every matching `report_run.window_start` and `window_end` points at
  yesterday.
- Every report-backed `freshness_watermark.last_successful_window_end` equals
  yesterday.

Fail if:

- Any default rehearsal row points at today.
- Any surface stores inconsistent window boundaries across `ingestion_job`,
  `report_run`, and `freshness_watermark`.

Same-day requests are only valid when an operator intentionally overrides the
lag for a separate experiment. They are a failure for the default acceptance
rehearsal.

### `warehouse_validation` results

The validation job compares the warehouse against current live outputs for:

- `get_keyword_performance`
- `get_search_term_report`
- `get_campaign_budget_history`
- `get_placement_report`
- `get_impression_share_report`
- `list_portfolios`
- `get_portfolio_budget_usage`

Run:

```sql
WITH params AS (
  SELECT
    '1234567890'::text AS profile_id,
    'na'::text AS region,
    TIMESTAMPTZ '2026-04-28T00:00:00Z' AS run_started_at
)
SELECT
  status,
  diagnostic_json->>'matched' AS matched,
  diagnostic_json->'results' AS results
FROM ingestion_job
WHERE profile_id = (SELECT profile_id FROM params)
  AND region = (SELECT region FROM params)
  AND surface_name = 'warehouse_validation'
  AND started_at >= (SELECT run_started_at FROM params)
ORDER BY started_at DESC
LIMIT 1;
```

Pass if:

- `status = 'completed'`
- `matched = 'true'`
- Every entry in `results` reports `matched = true`

Fail if the job is `failed`, if `matched = 'false'`, or if any validation
surface is missing from the result list.

### Warehouse-prefixed read-tool provenance

After the worker run, use your normal MCP client against the same profile and
region to verify cached-read behavior.

Required checks:

1. Call `warehouse_get_surface_status`.
2. Call at least one warehouse-prefixed report tool for the rehearsal window,
   such as `warehouse_get_keyword_performance`.
3. Call the same tool once with `read_preference="live_only"` as a control.

Pass if:

- `warehouse_get_surface_status` reports `status = 'available'` for the
  expected surfaces.
- The cached-read tool returns `provenance.data_source = 'warehouse'` with
  `provenance.read_preference = 'prefer_warehouse'`.
- `provenance.freshness.last_successful_window_end` matches the watermark you
  inspected in Postgres.
- The `live_only` control returns `provenance.data_source = 'live'` and
  `provenance.fallback_reason.code = 'live_only_requested'`.

Fail if a fresh surface falls back to live unexpectedly, if provenance fields do
not match the persisted watermark state, if `warehouse_get_surface_status`
shows any `status` other than `available` for a surface that the rehearsal was
supposed to verify, or if that surface reports `last_status` of `failed` or
`mismatch`.

## Negative-Path Verification

Run one expected failure to prove the worker rejects an invalid
profile-region combination before report creation.

1. Keep the same valid region.
2. Replace `WAREHOUSE_PROFILE_IDS` with a profile id that is not visible in that
   region.
3. Re-run the worker:

```bash
WAREHOUSE_PROFILE_IDS="999999999999" \
uv run python -m amazon_ads_mcp.warehouse.worker_entrypoint --run-once
```

Pass if:

- The process exits non-zero before any report is created.
- The console shows:
  `Configured warehouse profile IDs are not visible in region <region>: <ids>.`
- No new `report_run` rows are created for the invalid profile id.

Record the failing command output as evidence. This negative-path failure is an
expected success condition for the rehearsal.

## Known Limits

- `warehouse_validation` is sampled, not exhaustive. The validation helpers call
  the live report tools with `limit=100`, validate portfolio dimensions with up
  to 100 live rows, and validate portfolio usage against up to 25 visible
  portfolios.
- `WAREHOUSE_SCHEDULER_ENABLED=false` proves deterministic one-shot behavior,
  not recurring scheduler cadence.
- A passing rehearsal covers only the chosen profile and region. It does not
  prove multi-profile concurrency or every region.
- Availability-limited Amazon surfaces can still pass through matching
  diagnostics even when the metric rows themselves are sparse or unavailable.

## Optional Follow-Up Soak Check

After the deterministic rehearsal passes, you can run a separate scheduler soak
check:

1. Re-enable `WAREHOUSE_SCHEDULER_ENABLED=true`.
2. Leave the profile and region scope unchanged.
3. Observe at least one recurring interval for dimensions, reports, snapshots,
   and validation.
4. Re-check `ingestion_job` and `freshness_watermark` for duplicate claims,
   overlapping active work, or stale heartbeats.

Treat the soak check as additional confidence, not as a replacement for the
bounded `--run-once` rehearsal above.
