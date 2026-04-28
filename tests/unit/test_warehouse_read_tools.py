from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine

from amazon_ads_mcp.warehouse.read_tools import (
    warehouse_get_impression_share_report,
    warehouse_get_keyword_performance,
    warehouse_get_portfolio_budget_usage,
    warehouse_get_search_term_report,
    warehouse_get_surface_status,
)
from amazon_ads_mcp.warehouse.schema import metadata


@pytest.fixture
def warehouse_engine(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata.create_all(engine)

    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.db.get_warehouse_engine",
        lambda: engine,
    )
    return engine


@pytest.fixture
def sp_context(monkeypatch):
    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.require_sp_context",
        lambda: (object(), "profile-1", "na"),
    )


@pytest.fixture
def portfolio_context(monkeypatch):
    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.require_portfolio_context",
        lambda: (object(), "profile-1", "na"),
    )


def _seed_profile(engine):
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            INSERT INTO ads_profile (
                profile_id, region, first_seen_at, last_refreshed_at
            ) VALUES (
                'profile-1', 'na', '2026-01-10T00:00:00+00:00',
                '2026-01-10T00:00:00+00:00'
            )
            """
        )


def _seed_keyword_warehouse(engine):
    _seed_profile(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            INSERT INTO freshness_watermark (
                surface_name, profile_id, region, last_successful_window_end,
                last_snapshot_at, last_attempted_at, last_status, notes_json
            ) VALUES (
                'get_keyword_performance', 'profile-1', 'na', '2026-01-10',
                '2026-01-10T00:30:00+00:00', '2026-01-10T00:30:00+00:00',
                'completed', '{}'
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO ingestion_job (
                ingestion_job_id, job_key, job_type, surface_name, profile_id,
                region, window_start, window_end, scheduled_at, status,
                scope_json, diagnostic_json, attempt_count
            ) VALUES (
                'job-1', 'job-key-1', 'report', 'get_keyword_performance',
                'profile-1', 'na', '2026-01-10', '2026-01-10',
                '2026-01-10T00:00:00+00:00', 'completed', '{}', '{}', 1
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO report_run (
                report_run_id, ingestion_job_id, profile_id, window_start,
                window_end, surface_name, report_type_id, request_scope_hash,
                active_scope_key, status, requested_at, retrieved_at, row_count,
                diagnostic_json
            ) VALUES (
                'run-1', 'job-1', 'profile-1', '2026-01-10', '2026-01-10',
                'get_keyword_performance', 'spTargeting', 'scope-1', NULL,
                'completed', '2026-01-10T00:00:00+00:00',
                '2026-01-10T00:20:00+00:00', 1, '{}'
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO sp_keyword_performance_fact (
                profile_id, window_start, window_end, keyword_id, campaign_id,
                ad_group_id, keyword_text, match_type, current_bid,
                impressions, clicks, spend, sales_14d, orders_14d,
                last_report_run_id, retrieved_at
            ) VALUES (
                'profile-1', '2026-01-10', '2026-01-10', 'kw-1', 'camp-1',
                'ag-1', 'boots', 'BROAD', 1.5, 100, 10, 25, 200, 4,
                'run-1', '2026-01-10T00:20:00+00:00'
            )
            """
        )


def _seed_keyword_warehouse_incomplete(engine):
    _seed_profile(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            INSERT INTO freshness_watermark (
                surface_name, profile_id, region, last_successful_window_end,
                last_snapshot_at, last_attempted_at, last_status, notes_json
            ) VALUES (
                'get_keyword_performance', 'profile-1', 'na', '2026-01-10',
                '2026-01-10T00:30:00+00:00', '2026-01-10T00:30:00+00:00',
                'completed', '{}'
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO ingestion_job (
                ingestion_job_id, job_key, job_type, surface_name, profile_id,
                region, window_start, window_end, scheduled_at, status,
                scope_json, diagnostic_json, attempt_count
            ) VALUES (
                'job-oversized', 'job-key-oversized', 'report',
                'get_keyword_performance', 'profile-1', 'na',
                '2026-01-10', '2026-01-10',
                '2026-01-10T00:00:00+00:00', 'completed', '{}', '{}', 1
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO report_run (
                report_run_id, ingestion_job_id, profile_id, window_start,
                window_end, surface_name, report_type_id, request_scope_hash,
                active_scope_key, status, requested_at, retrieved_at, row_count,
                diagnostic_json
            ) VALUES (
                'run-oversized', 'job-oversized', 'profile-1',
                '2026-01-10', '2026-01-10', 'get_keyword_performance',
                'spTargeting', 'scope-oversized', NULL, 'completed',
                '2026-01-10T00:00:00+00:00', '2026-01-10T00:20:00+00:00',
                101, '{}'
            )
            """
        )


def _seed_portfolio_warehouse(engine, *, now: datetime | None = None):
    current = now or datetime.now(UTC)
    snapshot_at = current.replace(microsecond=0)
    usage_updated_at = snapshot_at.replace(minute=max(snapshot_at.minute - 1, 0))
    _seed_profile(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"""
            INSERT INTO freshness_watermark (
                surface_name, profile_id, region, last_snapshot_at,
                last_attempted_at, last_status, notes_json
            ) VALUES (
                'get_portfolio_budget_usage', 'profile-1', 'na',
                '{snapshot_at.isoformat()}', '{snapshot_at.isoformat()}',
                'completed', '{{}}'
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO portfolio (
                profile_id, portfolio_id, name, state, budget_scope,
                daily_budget, currency_code, budget_policy, in_budget,
                serving_status, campaign_unspent_budget_sharing_state,
                status_reasons_json, budget_start_date, budget_end_date,
                first_seen_at, last_refreshed_at
            ) VALUES (
                'profile-1', 'pt-1', 'Warehouse Portfolio', 'ENABLED', 'daily',
                100, 'USD', 'DAILY', 1, 'SERVING', NULL, '[]', NULL, NULL,
                '2026-01-10T00:00:00+00:00', '2026-01-10T00:00:00+00:00'
            )
            """
        )
        connection.exec_driver_sql(
            f"""
            INSERT INTO portfolio_budget_usage_snapshot (
                profile_id, portfolio_id, snapshot_timestamp, cap_amount,
                current_spend, remaining_budget, utilization_pct,
                usage_updated_timestamp, availability_state,
                availability_reason, diagnostic_json
            ) VALUES (
                'profile-1', 'pt-1', '{snapshot_at.isoformat()}', 100, 25, 75,
                25, '{usage_updated_at.isoformat()}', 'available', NULL,
                '{{"row_availability": {{"state": "available", "reason": null, "missing_fields": []}}, "diagnostic": {{}}}}'
            )
            """
        )


@pytest.mark.asyncio
async def test_warehouse_keyword_performance_reads_from_warehouse(
    monkeypatch,
    warehouse_engine,
    sp_context,
):
    _seed_keyword_warehouse(warehouse_engine)

    async def fail_live(**kwargs):
        raise AssertionError("live fallback should not run")

    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.get_keyword_performance",
        fail_live,
    )
    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.utcnow",
        lambda: datetime(2026, 1, 10, 0, 45, tzinfo=UTC),
    )

    result = await warehouse_get_keyword_performance(
        start_date="2026-01-10",
        end_date="2026-01-10",
        max_staleness_minutes=30,
    )

    assert result["returned_count"] == 1
    assert result["rows"][0]["keyword_id"] == "kw-1"
    assert result["provenance"]["data_source"] == "warehouse"
    assert result["provenance"]["freshness"]["freshness_status"] == "fresh"


@pytest.mark.asyncio
async def test_warehouse_keyword_performance_falls_back_when_stale(
    monkeypatch,
    warehouse_engine,
    sp_context,
):
    _seed_keyword_warehouse(warehouse_engine)

    async def fake_live(**kwargs):
        return {
            "profile_id": "profile-1",
            "region": "na",
            "start_date": kwargs["start_date"],
            "end_date": kwargs["end_date"],
            "report_id": "live-rpt",
            "filters": {
                "campaign_ids": [],
                "ad_group_ids": [],
                "keyword_ids": [],
                "limit": 100,
                "resume_from_report_id": None,
                "timeout_seconds": kwargs["timeout_seconds"],
            },
            "rows": [],
            "returned_count": 0,
        }

    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.get_keyword_performance",
        fake_live,
    )
    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.utcnow",
        lambda: datetime(2026, 1, 10, 2, 0, tzinfo=UTC),
    )

    result = await warehouse_get_keyword_performance(
        start_date="2026-01-10",
        end_date="2026-01-10",
        max_staleness_minutes=30,
    )

    assert result["report_id"] == "live-rpt"
    assert result["provenance"]["data_source"] == "live"
    assert result["provenance"]["fallback_reason"]["code"] == "stale_data"


@pytest.mark.asyncio
async def test_warehouse_keyword_performance_reports_warehouse_only_unavailable(
    monkeypatch,
    warehouse_engine,
    sp_context,
):
    _seed_keyword_warehouse(warehouse_engine)
    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.utcnow",
        lambda: datetime(2026, 1, 10, 2, 0, tzinfo=UTC),
    )

    result = await warehouse_get_keyword_performance(
        start_date="2026-01-10",
        end_date="2026-01-10",
        read_preference="warehouse_only",
        max_staleness_minutes=30,
    )

    assert result["rows"] == []
    assert result["provenance"]["data_source"] == "warehouse_unavailable"
    assert result["provenance"]["fallback_reason"]["code"] == "stale_data"


@pytest.mark.asyncio
async def test_warehouse_keyword_performance_falls_back_when_coverage_incomplete(
    monkeypatch,
    warehouse_engine,
    sp_context,
):
    _seed_keyword_warehouse_incomplete(warehouse_engine)

    async def fake_live(**kwargs):
        return {
            "profile_id": "profile-1",
            "region": "na",
            "start_date": kwargs["start_date"],
            "end_date": kwargs["end_date"],
            "report_id": "live-rpt-incomplete",
            "filters": {
                "campaign_ids": [],
                "ad_group_ids": [],
                "keyword_ids": [],
                "limit": 100,
                "resume_from_report_id": None,
                "timeout_seconds": kwargs["timeout_seconds"],
            },
            "rows": [],
            "returned_count": 0,
        }

    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.get_keyword_performance",
        fake_live,
    )
    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.utcnow",
        lambda: datetime(2026, 1, 10, 0, 45, tzinfo=UTC),
    )

    result = await warehouse_get_keyword_performance(
        start_date="2026-01-10",
        end_date="2026-01-10",
        max_staleness_minutes=30,
    )

    assert result["report_id"] == "live-rpt-incomplete"
    assert result["provenance"]["data_source"] == "live"
    assert (
        result["provenance"]["fallback_reason"]["code"]
        == "incomplete_coverage"
    )


@pytest.mark.asyncio
async def test_warehouse_impression_share_reports_unsupported_scope(
    monkeypatch,
    warehouse_engine,
    sp_context,
):
    _seed_profile(warehouse_engine)

    async def fail_live(**kwargs):
        raise AssertionError("live fallback should not run")

    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.get_impression_share_report",
        fail_live,
    )

    result = await warehouse_get_impression_share_report(
        start_date="2026-01-10",
        end_date="2026-01-10",
        campaign_ids=["camp-1"],
        ad_group_ids=["ag-1"],
        read_preference="warehouse_only",
    )

    assert result["availability"]["state"] == "unsupported"
    assert result["provenance"]["data_source"] == "warehouse_unavailable"
    assert result["provenance"]["fallback_reason"]["code"] == "unsupported_scope"


@pytest.mark.asyncio
async def test_warehouse_portfolio_budget_usage_reads_from_warehouse(
    monkeypatch,
    warehouse_engine,
    portfolio_context,
):
    _seed_portfolio_warehouse(warehouse_engine)

    async def fail_live(portfolio_ids):
        raise AssertionError("live fallback should not run")

    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.get_portfolio_budget_usage",
        fail_live,
    )
    result = await warehouse_get_portfolio_budget_usage(
        portfolio_ids=["pt-1"],
        max_staleness_minutes=30,
    )

    assert result["returned_count"] == 1
    assert result["rows"][0]["portfolio_id"] == "pt-1"
    assert result["provenance"]["data_source"] == "warehouse"


@pytest.mark.asyncio
async def test_warehouse_portfolio_budget_usage_falls_back_when_snapshot_missing(
    monkeypatch,
    warehouse_engine,
    portfolio_context,
):
    _seed_profile(warehouse_engine)

    async def fake_live(portfolio_ids):
        return {
            "profile_id": "profile-1",
            "region": "na",
            "filters": {"portfolio_ids": portfolio_ids},
            "availability": {
                "state": "available",
                "reason": None,
                "missing_portfolio_ids": [],
            },
            "diagnostics": [],
            "rows": [],
            "returned_count": 0,
        }

    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.get_portfolio_budget_usage",
        fake_live,
    )

    result = await warehouse_get_portfolio_budget_usage(portfolio_ids=["pt-1"])

    assert result["provenance"]["data_source"] == "live"
    assert result["provenance"]["fallback_reason"]["code"] in {
        "missing_freshness",
        "missing_data",
    }


@pytest.mark.asyncio
async def test_warehouse_surface_status_reports_missing_records(
    warehouse_engine,
    sp_context,
):
    _seed_profile(warehouse_engine)

    result = await warehouse_get_surface_status(
        surface_name="get_keyword_performance"
    )

    assert result["returned_count"] == 1
    assert result["surface_statuses"][0]["status"] == "missing"
    assert result["provenance"]["data_source"] == "warehouse"


@pytest.mark.asyncio
async def test_warehouse_surface_status_accepts_shared_controls(
    warehouse_engine,
    sp_context,
):
    _seed_profile(warehouse_engine)

    result = await warehouse_get_surface_status(
        surface_name="get_keyword_performance",
        read_preference="warehouse_only",
        max_staleness_minutes=15,
    )

    assert result["returned_count"] == 1
    assert result["provenance"]["read_preference"] == "warehouse_only"
    assert (
        result["provenance"]["freshness"]["max_staleness_minutes"] == 15
    )


@pytest.mark.asyncio
async def test_warehouse_search_term_live_only_attaches_provenance(
    monkeypatch,
    warehouse_engine,
    sp_context,
):
    _seed_profile(warehouse_engine)

    async def fake_live(**kwargs):
        return {
            "profile_id": "profile-1",
            "region": "na",
            "start_date": kwargs["start_date"],
            "end_date": kwargs["end_date"],
            "report_id": "live-search",
            "filters": {
                "campaign_ids": [],
                "limit": 100,
                "resume_from_report_id": None,
            },
            "rows": [],
            "returned_count": 0,
        }

    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.read_tools.get_search_term_report",
        fake_live,
    )

    result = await warehouse_get_search_term_report(
        start_date="2026-01-10",
        end_date="2026-01-10",
        read_preference="live_only",
    )

    assert result["report_id"] == "live-search"
    assert result["provenance"]["data_source"] == "live"
    assert result["provenance"]["fallback_reason"]["code"] == "live_only_requested"
