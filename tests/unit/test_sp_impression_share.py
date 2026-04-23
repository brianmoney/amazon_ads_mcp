from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.sp import impression_share as impression_share_module
from amazon_ads_mcp.tools.sp.report_helper import SPReportError


@pytest.mark.asyncio
async def test_get_impression_share_report_returns_normalized_rows(monkeypatch):
    fake_client = SimpleNamespace()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        impression_share_module,
        "require_sp_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        impression_share_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    run_report = AsyncMock(
        return_value={
            "report_id": "rpt-impression-1",
            "rows": [
                {
                    "campaignId": 10,
                    "campaignName": "Campaign A",
                    "adGroupId": 20,
                    "adGroupName": "Ad Group A",
                    "keywordId": 30,
                    "keyword": "running shoes",
                    "matchType": "EXACT",
                    "impressionShare": 0.63,
                    "lostImpressionShareBudget": 0.21,
                    "lostImpressionShareRank": 0.16,
                },
                {
                    "campaignId": 11,
                    "keywordId": 31,
                    "impressionShare": 0.40,
                },
            ],
        }
    )
    monkeypatch.setattr(impression_share_module, "run_sp_report", run_report)

    result = await impression_share_module.get_impression_share_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
        campaign_ids=[10],
        ad_group_ids=[20],
        keyword_ids=[30],
    )

    assert result["report_id"] == "rpt-impression-1"
    assert result["availability"]["state"] == "available"
    assert result["returned_count"] == 1
    assert result["rows"][0] == {
        "campaign_id": "10",
        "campaign_name": "Campaign A",
        "ad_group_id": "20",
        "ad_group_name": "Ad Group A",
        "keyword_id": "30",
        "keyword_text": "running shoes",
        "match_type": "EXACT",
        "impression_share": 63.0,
        "lost_is_budget": 21.0,
        "lost_is_rank": 16.0,
    }
    assert run_report.await_args.kwargs["report_type_id"] == "spTargeting"
    assert run_report.await_args.kwargs["group_by"] == ["targeting"]
    assert run_report.await_args.kwargs["filters"] == [
        {"field": "keywordType", "values": ["BROAD", "PHRASE", "EXACT"]}
    ]


@pytest.mark.asyncio
async def test_get_impression_share_report_resumes_completed_report(monkeypatch):
    fake_client = SimpleNamespace()
    manager = SimpleNamespace()
    run_report = AsyncMock()
    resume_report = AsyncMock(
        return_value={
            "report_id": "rpt-resume",
            "rows": [{"campaignId": 10, "keywordId": 30, "impressionShare": 80}],
        }
    )

    monkeypatch.setattr(
        impression_share_module,
        "require_sp_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        impression_share_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(impression_share_module, "run_sp_report", run_report)
    monkeypatch.setattr(impression_share_module, "resume_sp_report", resume_report)

    result = await impression_share_module.get_impression_share_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
        resume_from_report_id="rpt-resume",
    )

    assert result["report_id"] == "rpt-resume"
    assert result["filters"]["resume_from_report_id"] == "rpt-resume"
    run_report.assert_not_called()
    resume_report.assert_awaited_once_with("rpt-resume", client=fake_client)


@pytest.mark.asyncio
async def test_get_impression_share_report_surfaces_non_ready_resume(monkeypatch):
    fake_client = SimpleNamespace()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        impression_share_module,
        "require_sp_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        impression_share_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        impression_share_module,
        "resume_sp_report",
        AsyncMock(side_effect=SPReportError("not ready (status: PROCESSING)")),
    )

    with pytest.raises(SPReportError, match="PROCESSING"):
        await impression_share_module.get_impression_share_report(
            start_date="2026-01-01",
            end_date="2026-01-31",
            resume_from_report_id="rpt-pending",
        )


@pytest.mark.asyncio
async def test_get_impression_share_report_preserves_sparse_optional_fields(monkeypatch):
    fake_client = SimpleNamespace()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        impression_share_module,
        "require_sp_context",
        lambda: (manager, "profile-1", "eu"),
    )
    monkeypatch.setattr(
        impression_share_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        impression_share_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-impression-2",
                "rows": [
                    {
                        "campaignId": 10,
                        "targetId": 40,
                        "searchTermImpressionShare": "75",
                        "searchTermImpressionShareLostToBudget": "",
                        "searchTermImpressionShareLostToRank": None,
                    }
                ],
            }
        ),
    )

    result = await impression_share_module.get_impression_share_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    assert result["rows"][0] == {
        "campaign_id": "10",
        "campaign_name": None,
        "ad_group_id": None,
        "ad_group_name": None,
        "keyword_id": "40",
        "keyword_text": None,
        "match_type": None,
        "impression_share": 75.0,
        "lost_is_budget": None,
        "lost_is_rank": None,
    }


@pytest.mark.asyncio
async def test_get_impression_share_report_identifies_partial_scope_coverage(monkeypatch):
    fake_client = SimpleNamespace()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        impression_share_module,
        "require_sp_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        impression_share_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        impression_share_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-impression-3",
                "rows": [{"campaignId": 10, "keywordId": 30, "impressionShare": 70}],
            }
        ),
    )

    result = await impression_share_module.get_impression_share_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
        campaign_ids=[10, 11],
        keyword_ids=[30, 31],
    )

    assert result["returned_count"] == 1
    assert result["availability"] == {
        "state": "partial",
        "reason": "Impression-share data was only available for part of the requested scope.",
        "missing_campaign_ids": ["11"],
        "missing_ad_group_ids": [],
        "missing_keyword_ids": ["31"],
    }


@pytest.mark.asyncio
async def test_get_impression_share_report_returns_explicit_ineligible_outcome(monkeypatch):
    fake_client = SimpleNamespace()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        impression_share_module,
        "require_sp_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        impression_share_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        impression_share_module,
        "run_sp_report",
        AsyncMock(
            side_effect=SPReportError(
                "Sponsored Products report creation failed.",
                status_code=403,
                response_text="Brand Registry enrollment required for this report",
            )
        ),
    )

    result = await impression_share_module.get_impression_share_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
        campaign_ids=[10],
    )

    assert result["returned_count"] == 0
    assert result["rows"] == []
    assert result["availability"]["state"] == "ineligible"
    assert result["availability"]["missing_campaign_ids"] == ["10"]


@pytest.mark.asyncio
async def test_get_impression_share_report_returns_explicit_scope_unavailable_outcome(
    monkeypatch,
):
    fake_client = SimpleNamespace()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        impression_share_module,
        "require_sp_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        impression_share_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        impression_share_module,
        "run_sp_report",
        AsyncMock(return_value={"report_id": "rpt-impression-4", "rows": []}),
    )

    result = await impression_share_module.get_impression_share_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
        campaign_ids=[10],
        keyword_ids=[30],
    )

    assert result["availability"] == {
        "state": "unavailable",
        "reason": "Impression-share data could not be retrieved for the requested scope.",
        "missing_campaign_ids": ["10"],
        "missing_ad_group_ids": [],
        "missing_keyword_ids": ["30"],
    }
