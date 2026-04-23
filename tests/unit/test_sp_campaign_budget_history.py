import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from amazon_ads_mcp.tools.sp import campaign_budget_history as budget_history_module
from amazon_ads_mcp.tools.sp.report_helper import SPReportError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self):
        self.calls = []

    async def post(self, path, json=None, headers=None):
        self.calls.append((path, json, headers))
        assert path == "/sp/campaigns/list"
        return FakeResponse(
            {
                "campaigns": [
                    {
                        "campaignId": 11,
                        "name": "Recovered Campaign",
                    }
                ]
            }
        )


@pytest.mark.asyncio
async def test_get_campaign_budget_history_returns_normalized_rows(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        budget_history_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        budget_history_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    run_report = AsyncMock(
        return_value={
            "report_id": "rpt-budget-1",
            "rows": [
                {
                    "campaignId": 10,
                    "campaignName": "Campaign A",
                    "date": "2026-01-01",
                    "dailyBudget": 100,
                    "cost": 75,
                    "hoursRan": 18,
                },
                {
                    "campaignId": 11,
                    "reportDate": "2026-01-02",
                    "budget": 40,
                    "spend": 10,
                    "hours_ran": None,
                },
                {
                    "campaignId": 12,
                    "date": "2026-01-03",
                    "dailyBudget": 20,
                    "cost": 5,
                },
            ],
        }
    )
    monkeypatch.setattr(budget_history_module, "run_sp_report", run_report)

    result = await budget_history_module.get_campaign_budget_history(
        start_date="2026-01-01",
        end_date="2026-01-31",
        campaign_ids=[10, 11],
    )

    first, second = result["rows"]
    assert result["report_id"] == "rpt-budget-1"
    assert result["returned_count"] == 2
    assert first == {
        "date": "2026-01-01",
        "campaign_id": "10",
        "campaign_name": "Campaign A",
        "daily_budget": 100.0,
        "spend": 75.0,
        "utilization_pct": 75.0,
        "hours_ran": 18.0,
    }
    assert second == {
        "date": "2026-01-02",
        "campaign_id": "11",
        "campaign_name": "Recovered Campaign",
        "daily_budget": 40.0,
        "spend": 10.0,
        "utilization_pct": 25.0,
        "hours_ran": None,
    }
    assert fake_client.calls[0][1] == {
        "count": 1,
        "campaignIdFilter": {"include": ["11"]},
    }
    assert fake_client.calls[0][2] == {
        "Content-Type": "application/vnd.spCampaign.v3+json",
        "Accept": "application/vnd.spCampaign.v3+json",
    }
    assert run_report.await_args.kwargs["report_type_id"] == "budgetUsage"
    assert run_report.await_args.kwargs["group_by"] == ["campaign"]
    assert run_report.await_args.kwargs["time_unit"] == "DAILY"


@pytest.mark.asyncio
async def test_get_campaign_budget_history_resumes_completed_report(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()
    run_report = AsyncMock()
    resume_report = AsyncMock(
        return_value={
            "report_id": "rpt-resume",
            "rows": [
                {
                    "campaignId": 10,
                    "campaignName": "Campaign A",
                    "date": "2026-01-01",
                    "dailyBudget": 20,
                    "cost": 10,
                }
            ],
        }
    )

    monkeypatch.setattr(
        budget_history_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        budget_history_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(budget_history_module, "run_sp_report", run_report)
    monkeypatch.setattr(budget_history_module, "resume_sp_report", resume_report)

    result = await budget_history_module.get_campaign_budget_history(
        start_date="2026-01-01",
        end_date="2026-01-31",
        resume_from_report_id="rpt-resume",
    )

    assert result["report_id"] == "rpt-resume"
    assert result["filters"]["resume_from_report_id"] == "rpt-resume"
    run_report.assert_not_called()
    resume_report.assert_awaited_once_with("rpt-resume", client=fake_client)


@pytest.mark.asyncio
async def test_get_campaign_budget_history_surfaces_non_ready_resume(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        budget_history_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        budget_history_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        budget_history_module,
        "resume_sp_report",
        AsyncMock(side_effect=SPReportError("not ready (status: PROCESSING)")),
    )

    with pytest.raises(SPReportError, match="PROCESSING"):
        await budget_history_module.get_campaign_budget_history(
            start_date="2026-01-01",
            end_date="2026-01-31",
            resume_from_report_id="rpt-pending",
        )


@pytest.mark.asyncio
async def test_get_campaign_budget_history_preserves_sparse_optional_fields(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        budget_history_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        budget_history_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        budget_history_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-budget-2",
                "rows": [
                    {
                        "campaignId": 10,
                        "day": "2026-01-05",
                        "campaignBudgetAmount": "0",
                        "cost": "5",
                        "hoursActive": "",
                    }
                ],
            }
        ),
    )

    result = await budget_history_module.get_campaign_budget_history(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    row = result["rows"][0]
    assert row["date"] == "2026-01-05"
    assert row["campaign_name"] is None
    assert row["daily_budget"] == 0.0
    assert row["spend"] == 5.0
    assert row["utilization_pct"] is None
    assert row["hours_ran"] is None


@pytest.mark.asyncio
async def test_get_campaign_budget_history_surfaces_report_failures(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        budget_history_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        budget_history_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        budget_history_module,
        "run_sp_report",
        AsyncMock(side_effect=SPReportError("download failed")),
    )

    with pytest.raises(SPReportError, match="download failed"):
        await budget_history_module.get_campaign_budget_history(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )


@pytest.mark.asyncio
async def test_get_campaign_budget_history_logs_debug_when_campaign_lookup_fails(
    monkeypatch, caplog
):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        budget_history_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        budget_history_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        budget_history_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-budget-3",
                "rows": [{"campaignId": 10, "date": "2026-01-01", "cost": 5, "dailyBudget": 10}],
            }
        ),
    )
    monkeypatch.setattr(
        budget_history_module,
        "_fetch_campaign_name_context",
        AsyncMock(side_effect=httpx.HTTPError("campaign lookup failed")),
    )

    with caplog.at_level(logging.DEBUG, logger=budget_history_module.logger.name):
        result = await budget_history_module.get_campaign_budget_history(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )

    assert result["rows"][0]["campaign_name"] is None
    assert "Budget history campaign lookup failed" in caplog.text


@pytest.mark.asyncio
async def test_get_campaign_budget_history_does_not_hide_unexpected_lookup_errors(
    monkeypatch,
):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        budget_history_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        budget_history_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        budget_history_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-budget-4",
                "rows": [{"campaignId": 10, "date": "2026-01-01", "cost": 5, "dailyBudget": 10}],
            }
        ),
    )
    monkeypatch.setattr(
        budget_history_module,
        "_fetch_campaign_name_context",
        AsyncMock(side_effect=RuntimeError("unexpected programming error")),
    )

    with pytest.raises(RuntimeError, match="unexpected programming error"):
        await budget_history_module.get_campaign_budget_history(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )


@pytest.mark.asyncio
async def test_get_campaign_budget_history_rejects_invalid_window(monkeypatch):
    manager = SimpleNamespace()

    monkeypatch.setattr(
        budget_history_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )

    with pytest.raises(ValueError, match="start_date must be on or before end_date"):
        await budget_history_module.get_campaign_budget_history(
            start_date="2026-01-31",
            end_date="2026-01-01",
        )
