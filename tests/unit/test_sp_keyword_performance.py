from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.sp import keyword_performance as keyword_module
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
        assert path == "/sp/keywords/list"
        return FakeResponse({"keywords": [{"keywordId": 1, "bid": 1.25}]})


@pytest.mark.asyncio
async def test_get_keyword_performance_enriches_rows(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        keyword_module, "require_sp_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        keyword_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        keyword_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-1",
                "rows": [
                    {
                        "campaignId": 10,
                        "campaignName": "Campaign",
                        "adGroupId": 20,
                        "adGroupName": "Ad Group",
                        "keywordId": 1,
                        "keywordText": "shoes",
                        "matchType": "BROAD",
                        "impressions": 100,
                        "clicks": 10,
                        "cost": 25,
                        "sales14d": 200,
                        "orders14d": 4,
                    },
                    {
                        "campaignId": 99,
                        "adGroupId": 20,
                        "keywordId": 2,
                        "keyword": "ignored",
                    },
                ],
            }
        ),
    )

    result = await keyword_module.get_keyword_performance(
        start_date="2026-01-01",
        end_date="2026-01-31",
        campaign_ids=["10"],
    )

    row = result["rows"][0]
    assert result["report_id"] == "rpt-1"
    assert row["bid"] == 1.25
    assert row["ctr"] == 0.1
    assert row["cpc"] == 2.5
    assert row["acos"] == 0.125
    assert row["roas"] == 8.0
    assert result["returned_count"] == 1
    assert fake_client.calls[0][2] == {
        "Content-Type": "application/vnd.spKeyword.v3+json",
        "Accept": "application/vnd.spKeyword.v3+json",
    }
    assert fake_client.calls[0][1] == {
        "count": 100,
        "campaignIdFilter": {"include": ["10"]},
    }


@pytest.mark.asyncio
async def test_get_keyword_performance_handles_zero_and_null_metrics(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        keyword_module, "require_sp_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        keyword_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        keyword_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-2",
                "rows": [
                    {
                        "campaignId": 10,
                        "adGroupId": 20,
                        "keywordId": 1,
                        "keywordText": "shoes",
                        "impressions": 0,
                        "clicks": 0,
                        "cost": None,
                        "sales14d": 0,
                        "orders14d": None,
                    }
                ],
            }
        ),
    )

    result = await keyword_module.get_keyword_performance(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    row = result["rows"][0]
    assert row["ctr"] is None
    assert row["cpc"] is None
    assert row["acos"] is None
    assert row["roas"] is None


@pytest.mark.asyncio
async def test_get_keyword_performance_surfaces_report_failures(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        keyword_module, "require_sp_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        keyword_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        keyword_module,
        "run_sp_report",
        AsyncMock(side_effect=SPReportError("polling failed")),
    )

    with pytest.raises(SPReportError, match="polling failed"):
        await keyword_module.get_keyword_performance(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
