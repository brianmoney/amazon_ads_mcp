from datetime import date
from types import SimpleNamespace

import pytest

from amazon_ads_mcp.warehouse import worker as worker_module


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
