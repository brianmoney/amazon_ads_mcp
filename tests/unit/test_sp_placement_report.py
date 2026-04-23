import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from amazon_ads_mcp.tools.sp import placement_report as placement_module
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
                        "campaignId": 10,
                        "optimizations": {
                            "bidSettings": {
                                "bidAdjustments": {
                                    "placementBidAdjustments": [
                                        {
                                            "placement": "TOP_OF_SEARCH",
                                            "percentage": 50,
                                        },
                                        {
                                            "placement": "PRODUCT_PAGE",
                                            "percentage": 20,
                                        },
                                    ]
                                }
                            }
                        },
                    }
                ]
            }
        )


@pytest.mark.asyncio
async def test_get_placement_report_returns_normalized_rows(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        placement_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        placement_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    run_report = AsyncMock(
        return_value={
            "report_id": "rpt-placement-1",
            "rows": [
                {
                    "campaignId": 10,
                    "campaignName": "Campaign A",
                    "placementClassification": "TOP_OF_SEARCH",
                    "impressions": 1000,
                    "clicks": 50,
                    "cost": 25,
                    "sales14d": 200,
                    "purchases14d": 4,
                },
                {
                    "campaignId": 11,
                    "placementClassification": "REST_OF_SEARCH",
                },
            ],
        }
    )
    monkeypatch.setattr(placement_module, "run_sp_report", run_report)

    result = await placement_module.get_placement_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
        campaign_ids=[10],
    )

    row = result["rows"][0]
    assert result["report_id"] == "rpt-placement-1"
    assert result["returned_count"] == 1
    assert row == {
        "campaign_id": "10",
        "campaign_name": "Campaign A",
        "placement_type": "top_of_search",
        "impressions": 1000.0,
        "clicks": 50.0,
        "spend": 25.0,
        "sales14d": 200.0,
        "purchases14d": 4.0,
        "ctr": 0.05,
        "cpc": 0.5,
        "acos": 0.125,
        "roas": 8.0,
        "current_top_of_search_multiplier": 50.0,
        "current_product_pages_multiplier": 20.0,
    }
    assert fake_client.calls[0][1] == {
        "count": 1,
        "campaignIdFilter": ["10"],
    }
    assert fake_client.calls[0][2] == {
        "Content-Type": "application/vnd.spCampaign.v3+json",
        "Accept": "application/vnd.spCampaign.v3+json",
    }
    assert run_report.await_args.kwargs["report_type_id"] == "spCampaigns"
    assert run_report.await_args.kwargs["group_by"] == ["campaign", "campaignPlacement"]


@pytest.mark.asyncio
async def test_get_placement_report_resumes_completed_report(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()
    run_report = AsyncMock()
    resume_report = AsyncMock(
        return_value={
            "report_id": "rpt-resume",
            "rows": [
                {
                    "campaignId": 10,
                    "placementClassification": "PRODUCT_PAGE",
                }
            ],
        }
    )

    monkeypatch.setattr(
        placement_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        placement_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(placement_module, "run_sp_report", run_report)
    monkeypatch.setattr(placement_module, "resume_sp_report", resume_report)

    result = await placement_module.get_placement_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
        resume_from_report_id="rpt-resume",
    )

    assert result["report_id"] == "rpt-resume"
    assert result["filters"]["resume_from_report_id"] == "rpt-resume"
    run_report.assert_not_called()
    resume_report.assert_awaited_once_with("rpt-resume", client=fake_client)


@pytest.mark.asyncio
async def test_get_placement_report_surfaces_non_ready_resume(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        placement_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        placement_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        placement_module,
        "resume_sp_report",
        AsyncMock(side_effect=SPReportError("not ready (status: PROCESSING)")),
    )

    with pytest.raises(SPReportError, match="PROCESSING"):
        await placement_module.get_placement_report(
            start_date="2026-01-01",
            end_date="2026-01-31",
            resume_from_report_id="rpt-pending",
        )


@pytest.mark.asyncio
async def test_get_placement_report_preserves_rows_when_multiplier_lookup_fails(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        placement_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        placement_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        placement_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-placement-2",
                "rows": [
                    {
                        "campaignId": 10,
                        "campaignName": "Campaign A",
                        "placementClassification": "rest of search",
                        "impressions": 0,
                        "clicks": 0,
                        "cost": None,
                        "sales14d": 0,
                        "purchases14d": None,
                    }
                ],
            }
        ),
    )
    monkeypatch.setattr(
        placement_module,
        "_fetch_campaign_multiplier_context",
        AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "campaign lookup failed",
                request=httpx.Request("POST", "https://advertising-api.amazon.com"),
                response=httpx.Response(500),
            )
        ),
    )

    result = await placement_module.get_placement_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    row = result["rows"][0]
    assert row["placement_type"] == "rest_of_search"
    assert row["ctr"] is None
    assert row["cpc"] is None
    assert row["acos"] is None
    assert row["roas"] is None
    assert row["current_top_of_search_multiplier"] is None
    assert row["current_product_pages_multiplier"] is None


@pytest.mark.asyncio
async def test_get_placement_report_logs_debug_when_multiplier_lookup_fails(
    monkeypatch, caplog
):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        placement_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        placement_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        placement_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-placement-3",
                "rows": [{"campaignId": 10, "placementClassification": "TOP_OF_SEARCH"}],
            }
        ),
    )
    monkeypatch.setattr(
        placement_module,
        "_fetch_campaign_multiplier_context",
        AsyncMock(side_effect=httpx.HTTPError("campaign lookup failed")),
    )

    with caplog.at_level(logging.DEBUG, logger=placement_module.logger.name):
        await placement_module.get_placement_report(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )

    assert "Placement multiplier lookup failed" in caplog.text


@pytest.mark.asyncio
async def test_get_placement_report_does_not_hide_unexpected_multiplier_lookup_errors(
    monkeypatch,
):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        placement_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        placement_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        placement_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-placement-4",
                "rows": [{"campaignId": 10, "placementClassification": "TOP_OF_SEARCH"}],
            }
        ),
    )
    monkeypatch.setattr(
        placement_module,
        "_fetch_campaign_multiplier_context",
        AsyncMock(side_effect=RuntimeError("unexpected programming error")),
    )

    with pytest.raises(RuntimeError, match="unexpected programming error"):
        await placement_module.get_placement_report(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )


@pytest.mark.asyncio
async def test_get_placement_report_rejects_invalid_window(monkeypatch):
    manager = SimpleNamespace()

    monkeypatch.setattr(
        placement_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )

    with pytest.raises(ValueError, match="start_date must be on or before end_date"):
        await placement_module.get_placement_report(
            start_date="2026-01-31",
            end_date="2026-01-01",
        )
