from datetime import date
from types import SimpleNamespace

import pytest

from amazon_ads_mcp.warehouse import worker as worker_module
from amazon_ads_mcp.tools.sp.report_helper import SPReportError


class FakeJobCoordinator:
    def __init__(self):
        self.completed = []
        self.failed = []
        self.heartbeats = []

    def claim(self, scope, *, worker_id):
        self.scope = scope
        self.worker_id = worker_id
        return SimpleNamespace(ingestion_job_id="job-1")

    def complete(self, ingestion_job_id, *, diagnostic=None):
        self.completed.append((ingestion_job_id, diagnostic))

    def fail(self, ingestion_job_id, *, error_text, diagnostic=None):
        self.failed.append((ingestion_job_id, error_text, diagnostic))

    def heartbeat(self, ingestion_job_id):
        self.heartbeats.append(ingestion_job_id)


@pytest.mark.asyncio
async def test_run_validation_covers_all_in_scope_surfaces(monkeypatch):
    expected_surfaces = [
        "get_keyword_performance",
        "get_search_term_report",
        "get_campaign_budget_history",
        "get_placement_report",
        "get_impression_share_report",
        "list_portfolios",
        "get_portfolio_budget_usage",
    ]
    called_surfaces = []

    def make_validator(surface_name):
        async def _validator(*args, **kwargs):
            called_surfaces.append(surface_name)
            return {"surface_name": surface_name, "matched": True}

        return _validator

    monkeypatch.setattr(
        worker_module,
        "report_window",
        lambda settings: (date(2026, 1, 1), date(2026, 1, 2)),
    )
    monkeypatch.setattr(
        worker_module,
        "fetch_live_portfolios",
        make_validator("fetch_live_portfolios"),
    )
    monkeypatch.setattr(worker_module, "advance_watermark", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        worker_module,
        "validate_keyword_performance",
        make_validator("get_keyword_performance"),
    )
    monkeypatch.setattr(
        worker_module,
        "validate_search_terms",
        make_validator("get_search_term_report"),
    )
    monkeypatch.setattr(
        worker_module,
        "validate_budget_history",
        make_validator("get_campaign_budget_history"),
    )
    monkeypatch.setattr(
        worker_module,
        "validate_placement_report",
        make_validator("get_placement_report"),
    )
    monkeypatch.setattr(
        worker_module,
        "validate_impression_share",
        make_validator("get_impression_share_report"),
    )
    monkeypatch.setattr(
        worker_module,
        "validate_portfolios",
        make_validator("list_portfolios"),
    )
    monkeypatch.setattr(
        worker_module,
        "validate_portfolio_usage",
        make_validator("get_portfolio_budget_usage"),
    )

    async def fake_fetch_live_portfolios(*, limit):
        assert limit == 25
        return [{"portfolio_id": "portfolio-1"}]

    monkeypatch.setattr(
        worker_module,
        "fetch_live_portfolios",
        fake_fetch_live_portfolios,
    )

    warehouse_worker = worker_module.WarehouseWorker(
        settings=SimpleNamespace(
            warehouse_worker_id="worker-1",
            warehouse_heartbeat_seconds=60,
        )
    )
    coordinator = FakeJobCoordinator()

    await warehouse_worker._run_validation(
        connection=object(),
        job_coordinator=coordinator,
        profile_id="profile-1",
        region="na",
    )

    assert called_surfaces == expected_surfaces
    assert coordinator.failed == []
    assert len(coordinator.completed) == 1
    assert coordinator.heartbeats == ["job-1"]
    diagnostic = coordinator.completed[0][1]
    assert diagnostic["matched"] is True
    assert [result["surface_name"] for result in diagnostic["results"]] == expected_surfaces


@pytest.mark.asyncio
async def test_run_with_heartbeat_records_initial_heartbeat():
    warehouse_worker = worker_module.WarehouseWorker(
        settings=SimpleNamespace(
            warehouse_worker_id="worker-1",
            warehouse_heartbeat_seconds=60,
        )
    )
    coordinator = FakeJobCoordinator()

    async def fake_operation():
        await worker_module.asyncio.sleep(0)
        return "done"

    result = await warehouse_worker._run_with_heartbeat(
        coordinator,
        "job-1",
        fake_operation(),
    )

    assert result == "done"
    assert coordinator.heartbeats == ["job-1"]


@pytest.mark.asyncio
async def test_execute_report_surface_completes_when_poll_timeout_is_resumable(
    monkeypatch,
):
    monkeypatch.setattr(
        worker_module,
        "report_window",
        lambda settings: (date(2026, 1, 1), date(2026, 1, 2)),
    )

    class FakeDurableReports:
        def __init__(self, connection):
            self.connection = connection
            self.marked = []

        def create_or_resume(self, **kwargs):
            return SimpleNamespace(
                report_run_id="run-1",
                amazon_report_id="rpt-1",
            )

        def mark_polled(self, report_run_id, **kwargs):
            self.marked.append((report_run_id, kwargs))
            return SimpleNamespace(
                report_run_id=report_run_id,
                amazon_report_id="rpt-1",
            )

        def mark_downloaded(self, *args, **kwargs):
            raise AssertionError("download should not run for resumable timeout")

    durable = FakeDurableReports(object())
    monkeypatch.setattr(
        worker_module,
        "DurableReportCoordinator",
        lambda connection: durable,
    )

    async def fake_lookup(*args, **kwargs):
        return {"status": "QUEUED", "raw_status": "QUEUED", "status_details": None}

    async def fake_poll(*args, **kwargs):
        raise SPReportError(
            "Sponsored Products report rpt-1 timed out while polling after 360.0s "
            "(last status: QUEUED)."
        )

    monkeypatch.setattr(worker_module, "lookup_live_report_status", fake_lookup)
    monkeypatch.setattr(worker_module, "poll_live_report", fake_poll)

    async def fake_get_client(_auth_manager):
        return object()

    async def unexpected_create(*args, **kwargs):
        raise AssertionError("create_live_report should not run")

    async def unexpected_download(*args, **kwargs):
        raise AssertionError("download_live_report_rows should not run")

    async def unexpected_loader(*args, **kwargs):
        raise AssertionError("loader should not run")

    monkeypatch.setattr(worker_module, "create_live_report", unexpected_create)
    monkeypatch.setattr(
        worker_module, "download_live_report_rows", unexpected_download
    )
    monkeypatch.setattr(
        worker_module, "load_keyword_performance", unexpected_loader
    )

    monkeypatch.setattr(
        "amazon_ads_mcp.tools.sp.common.require_sp_context",
        lambda: (object(), "profile-1", "na"),
    )
    monkeypatch.setattr(
        "amazon_ads_mcp.tools.sp.common.get_sp_client",
        fake_get_client,
    )

    warehouse_worker = worker_module.WarehouseWorker(
        settings=SimpleNamespace(
            warehouse_worker_id="worker-1",
            warehouse_heartbeat_seconds=60,
            warehouse_report_poll_timeout_seconds=360.0,
        )
    )
    coordinator = FakeJobCoordinator()

    await warehouse_worker._execute_report_surface(
        connection=object(),
        job_coordinator=coordinator,
        profile_id="profile-1",
        region="na",
        surface_name="get_keyword_performance",
    )

    assert coordinator.completed == []
    assert len(coordinator.failed) == 1
    diagnostic = coordinator.failed[0][2]
    assert diagnostic["status"] == "deferred"
    assert diagnostic["amazon_report_id"] == "rpt-1"
    assert durable.marked[-1][1]["status"] == "queued"
    assert durable.marked[-1][1]["diagnostic"]["resumable"] is True


@pytest.mark.asyncio
async def test_resolve_profiles_for_region_rejects_invalid_configured_profiles(
    monkeypatch,
):
    seen_regions = []

    async def fake_ensure_region(region):
        seen_regions.append(region)

    async def fake_fetch_live_profiles():
        return [{"profileId": "profile-1"}, {"profileId": "profile-2"}]

    monkeypatch.setattr(worker_module, "ensure_worker_region", fake_ensure_region)
    monkeypatch.setattr(worker_module, "fetch_live_profiles", fake_fetch_live_profiles)

    warehouse_worker = worker_module.WarehouseWorker(
        settings=SimpleNamespace(
            warehouse_worker_id="worker-1",
            warehouse_heartbeat_seconds=60,
            effective_warehouse_profile_ids=["profile-1", "profile-9"],
        )
    )

    with pytest.raises(
        RuntimeError,
        match=r"Configured warehouse profile IDs are not visible in region na: profile-9",
    ):
        await warehouse_worker._resolve_profiles_for_region("na")

    assert seen_regions == ["na"]


@pytest.mark.asyncio
async def test_execute_report_surface_marks_create_failure_terminal(
    monkeypatch,
):
    monkeypatch.setattr(
        worker_module,
        "report_window",
        lambda settings: (date(2026, 1, 1), date(2026, 1, 2)),
    )

    class FakeDurableReports:
        def __init__(self, connection):
            self.connection = connection
            self.failed = []

        def create_or_resume(self, **kwargs):
            return SimpleNamespace(
                report_run_id="run-1",
                amazon_report_id=None,
            )

        def store_amazon_report_id(self, *args, **kwargs):
            raise AssertionError("store_amazon_report_id should not run")

        def mark_polled(self, *args, **kwargs):
            raise AssertionError("mark_polled should not run")

        def mark_downloaded(self, *args, **kwargs):
            raise AssertionError("mark_downloaded should not run")

        def mark_failed(self, report_run_id, **kwargs):
            self.failed.append((report_run_id, kwargs))
            return SimpleNamespace(report_run_id=report_run_id)

    durable = FakeDurableReports(object())
    monkeypatch.setattr(
        worker_module,
        "DurableReportCoordinator",
        lambda connection: durable,
    )

    async def fake_get_client(_auth_manager):
        return object()

    async def fake_create(*args, **kwargs):
        raise SPReportError(
            "Sponsored Products report creation failed. (status 400): invalid report configuration",
            status_code=400,
            response_text="invalid report configuration",
        )

    monkeypatch.setattr(worker_module, "create_live_report", fake_create)
    monkeypatch.setattr(
        "amazon_ads_mcp.tools.sp.common.require_sp_context",
        lambda: (object(), "profile-1", "na"),
    )
    monkeypatch.setattr(
        "amazon_ads_mcp.tools.sp.common.get_sp_client",
        fake_get_client,
    )

    warehouse_worker = worker_module.WarehouseWorker(
        settings=SimpleNamespace(
            warehouse_worker_id="worker-1",
            warehouse_heartbeat_seconds=60,
            warehouse_report_poll_timeout_seconds=360.0,
        )
    )
    coordinator = FakeJobCoordinator()

    with pytest.raises(SPReportError, match=r"status 400"):
        await warehouse_worker._execute_report_surface(
            connection=object(),
            job_coordinator=coordinator,
            profile_id="profile-1",
            region="na",
            surface_name="get_keyword_performance",
        )

    assert coordinator.completed == []
    assert len(coordinator.failed) == 1
    job_diagnostic = coordinator.failed[0][2]
    assert job_diagnostic == {
        "status": "failed",
        "phase": "create",
        "surface_name": "get_keyword_performance",
        "profile_id": "profile-1",
        "region": "na",
        "amazon_report_id": None,
        "request_window": {
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
        },
        "request": {
            "surface_name": "get_keyword_performance",
            "report_type_id": "spTargeting",
            "start_date": "2026-01-01",
            "end_date": "2026-01-02",
            "group_by": ["targeting"],
            "columns": [
                "campaignId",
                "campaignName",
                "adGroupId",
                "adGroupName",
                "keywordId",
                "keyword",
                "matchType",
                "impressions",
                "clicks",
                "cost",
                "sales14d",
                "purchases14d",
            ],
            "filters": [{"field": "keywordType", "values": ["BROAD", "PHRASE", "EXACT"]}],
            "time_unit": "SUMMARY",
        },
        "error": {
            "message": (
                "Sponsored Products report creation failed. "
                "(status 400): invalid report configuration"
            ),
            "status_code": 400,
            "response_text": "invalid report configuration",
        },
    }
    assert durable.failed == [
        (
            "run-1",
            {
                "error_text": (
                    "Sponsored Products report creation failed. "
                    "(status 400): invalid report configuration"
                ),
                "raw_status": "HTTP_400",
                "status_details": "invalid report configuration",
                "diagnostic": job_diagnostic,
            },
        )
    ]


def test_report_surfaces_use_supported_budget_history_report_contract():
    assert worker_module.REPORT_SURFACES["get_campaign_budget_history"] == {
        "report_type_id": "spCampaigns",
        "group_by": ["campaign"],
        "columns": [
            "campaignId",
            "campaignName",
            "date",
            "cost",
            "campaignBudgetAmount",
        ],
        "filters": [],
        "time_unit": "DAILY",
    }
