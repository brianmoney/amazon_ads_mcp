from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.sd import performance as performance_module
from amazon_ads_mcp.tools.sd.report_helper import SDReportError


@pytest.mark.asyncio
async def test_get_sd_performance_returns_normalized_rows(monkeypatch):
    manager = SimpleNamespace()

    monkeypatch.setattr(
        performance_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        performance_module, "get_sd_client", AsyncMock(return_value=SimpleNamespace())
    )
    run_report = AsyncMock(
        return_value={
            "report_id": "sd-rpt-1",
            "rows": [
                {
                    "campaignId": 10,
                    "campaignName": "Conversions",
                    "adGroupId": 20,
                    "adGroupName": "Viewed PDP",
                    "campaignObjective": "CONVERSIONS",
                    "biddingModel": "CPC",
                    "impressions": 1000,
                    "clicks": 50,
                    "cost": 125,
                    "sales": 500,
                    "purchases": 10,
                },
                {
                    "campaignId": 11,
                    "campaignName": "Reach",
                    "adGroupId": 21,
                    "campaignObjective": "REACH",
                    "impressions": 5000,
                    "impressionsViews": 4000,
                    "clicks": 5,
                    "cost": 24,
                    "sales": 0,
                    "purchases": 0,
                },
            ],
        }
    )
    monkeypatch.setattr(performance_module, "run_sd_report", run_report)

    result = await performance_module.get_sd_performance(
        start_date="2026-01-01",
        end_date="2026-01-31",
        campaign_ids=["10", "11"],
        objectives=["conversions", "reach"],
    )

    cpc_row = result["rows"][0]
    vcpm_row = result["rows"][1]
    assert result["report_id"] == "sd-rpt-1"
    assert cpc_row["ctr"] == 0.05
    assert cpc_row["cpc"] == 2.5
    assert cpc_row["acos"] == 0.25
    assert cpc_row["roas"] == 4.0
    assert vcpm_row["cpc"] is None
    assert vcpm_row["vcpm"] == 6.0
    assert vcpm_row["targeting_group_name"] is None
    assert result["returned_count"] == 2
    assert run_report.await_args.kwargs["filters"] == [
        {"field": "campaignObjective", "values": ["CONVERSIONS", "REACH"]}
    ]
    assert run_report.await_args.kwargs["report_type_id"] == "sdAdGroup"
    assert run_report.await_args.kwargs["group_by"] == ["adGroup"]


@pytest.mark.asyncio
async def test_get_sd_performance_preserves_sparse_optional_fields(monkeypatch):
    manager = SimpleNamespace()

    monkeypatch.setattr(
        performance_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        performance_module, "get_sd_client", AsyncMock(return_value=SimpleNamespace())
    )
    monkeypatch.setattr(
        performance_module,
        "run_sd_report",
        AsyncMock(
            return_value={
                "report_id": "sd-rpt-2",
                "rows": [
                    {
                        "campaignId": 10,
                        "adGroupId": 20,
                        "campaignObjective": "CONSIDERATION",
                        "impressions": 0,
                        "clicks": 0,
                        "cost": None,
                        "sales": None,
                        "purchases": None,
                    }
                ],
            }
        ),
    )

    result = await performance_module.get_sd_performance(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    row = result["rows"][0]
    assert row["campaign_name"] is None
    assert row["targeting_group_name"] is None
    assert row["ctr"] is None
    assert row["cpc"] is None
    assert row["acos"] is None
    assert row["roas"] is None


@pytest.mark.asyncio
async def test_get_sd_performance_resumes_completed_report(monkeypatch):
    manager = SimpleNamespace()

    monkeypatch.setattr(
        performance_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        performance_module, "get_sd_client", AsyncMock(return_value=SimpleNamespace())
    )
    run_report = AsyncMock()
    resume_report = AsyncMock(
        return_value={
            "report_id": "sd-rpt-resume",
            "rows": [{"campaignId": 10, "adGroupId": 20}],
        }
    )
    monkeypatch.setattr(performance_module, "run_sd_report", run_report)
    monkeypatch.setattr(performance_module, "resume_sd_report", resume_report)

    result = await performance_module.get_sd_performance(
        start_date="2026-01-01",
        end_date="2026-01-31",
        resume_from_report_id="sd-rpt-resume",
    )

    assert result["report_id"] == "sd-rpt-resume"
    assert result["filters"]["resume_from_report_id"] == "sd-rpt-resume"
    run_report.assert_not_called()
    resume_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_sd_performance_surfaces_report_failures(monkeypatch):
    manager = SimpleNamespace()

    monkeypatch.setattr(
        performance_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        performance_module, "get_sd_client", AsyncMock(return_value=SimpleNamespace())
    )
    monkeypatch.setattr(
        performance_module,
        "run_sd_report",
        AsyncMock(side_effect=SDReportError("polling failed")),
    )

    with pytest.raises(SDReportError, match="polling failed"):
        await performance_module.get_sd_performance(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )


def test_build_report_filters_uses_campaign_objective_field():
    assert performance_module._build_report_filters(["REACH"]) == [
        {"field": "campaignObjective", "values": ["REACH"]}
    ]


@pytest.mark.asyncio
async def test_get_sd_performance_surfaces_non_ready_resume(monkeypatch):
    manager = SimpleNamespace()

    monkeypatch.setattr(
        performance_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        performance_module, "get_sd_client", AsyncMock(return_value=SimpleNamespace())
    )
    monkeypatch.setattr(
        performance_module,
        "resume_sd_report",
        AsyncMock(side_effect=SDReportError("not ready (status: PROCESSING)")),
    )

    with pytest.raises(SDReportError, match="PROCESSING"):
        await performance_module.get_sd_performance(
            start_date="2026-01-01",
            end_date="2026-01-31",
            resume_from_report_id="sd-rpt-pending",
        )
