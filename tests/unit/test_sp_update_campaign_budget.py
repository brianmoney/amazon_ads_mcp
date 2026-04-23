import importlib

import httpx
import pytest

from amazon_ads_mcp.tools.sp.common import SPContextError


budget_module = importlib.import_module(
    "amazon_ads_mcp.tools.sp.update_campaign_budget"
)


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.request = httpx.Request("PUT", "https://example.com/sp/campaigns/cmp-1")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=self.request,
                response=httpx.Response(
                    self.status_code,
                    request=self.request,
                    json=self.payload,
                ),
            )

    def json(self):
        return self.payload

    @property
    def text(self):
        if isinstance(self.payload, dict):
            return str(self.payload)
        return ""


class FakeClient:
    def __init__(self, *, list_payload, put_response=None):
        self.post_calls = []
        self.put_calls = []
        self.list_payload = list_payload
        self.put_response = put_response or FakeResponse(
            {"campaignId": "cmp-1", "dailyBudget": 25.0}
        )

    async def post(self, path, json=None, headers=None):
        self.post_calls.append((path, json, headers))
        assert path == "/sp/campaigns/list"
        return FakeResponse(self.list_payload)

    async def put(self, path, json=None, headers=None):
        self.put_calls.append((path, json, headers))
        assert path == "/sp/campaigns/cmp-1"
        return self.put_response


@pytest.mark.asyncio
async def test_update_campaign_budget_returns_applied_result(monkeypatch):
    fake_client = FakeClient(
        list_payload={"campaigns": [{"campaignId": "cmp-1", "dailyBudget": 20.0}]},
        put_response=FakeResponse({"campaignId": "cmp-1", "dailyBudget": 25.0}),
    )

    async def fake_context():
        return object(), "profile-1", "na", fake_client

    monkeypatch.setattr(budget_module, "get_sp_write_context", fake_context)

    result = await budget_module.update_campaign_budget("cmp-1", 25.0)

    assert result["applied_count"] == 1
    assert result["skipped_count"] == 0
    assert result["failed_count"] == 0
    assert result["results"] == [
        {
            "outcome": "applied",
            "status": "UPDATED",
            "campaign_id": "cmp-1",
            "requested_daily_budget": 25.0,
            "previous_daily_budget": 20.0,
            "resulting_daily_budget": 25.0,
        }
    ]
    assert fake_client.put_calls[0][1] == {"dailyBudget": 25.0}


@pytest.mark.asyncio
async def test_update_campaign_budget_skips_noop_requests(monkeypatch):
    fake_client = FakeClient(
        list_payload={"campaigns": [{"campaignId": "cmp-1", "dailyBudget": 25.0}]}
    )

    async def fake_context():
        return object(), "profile-1", "eu", fake_client

    monkeypatch.setattr(budget_module, "get_sp_write_context", fake_context)

    result = await budget_module.update_campaign_budget("cmp-1", 25.0)

    assert result["applied_count"] == 0
    assert result["skipped_count"] == 1
    assert result["failed_count"] == 0
    assert result["results"] == [
        {
            "outcome": "skipped",
            "status": "ALREADY_SET",
            "campaign_id": "cmp-1",
            "requested_daily_budget": 25.0,
            "previous_daily_budget": 25.0,
            "resulting_daily_budget": 25.0,
        }
    ]
    assert fake_client.put_calls == []


@pytest.mark.asyncio
async def test_update_campaign_budget_surfaces_missing_context(monkeypatch):
    async def fake_context():
        raise SPContextError("missing profile")

    monkeypatch.setattr(budget_module, "get_sp_write_context", fake_context)

    with pytest.raises(SPContextError, match="missing profile"):
        await budget_module.update_campaign_budget("cmp-1", 25.0)


@pytest.mark.asyncio
async def test_update_campaign_budget_returns_failed_result_for_api_rejection(monkeypatch):
    fake_client = FakeClient(
        list_payload={"campaigns": [{"campaignId": "cmp-1", "dailyBudget": 20.0}]},
        put_response=FakeResponse(
            {"message": "Campaign is archived"},
            status_code=400,
        ),
    )

    async def fake_context():
        return object(), "profile-1", "na", fake_client

    monkeypatch.setattr(budget_module, "get_sp_write_context", fake_context)

    result = await budget_module.update_campaign_budget("cmp-1", 25.0)

    assert result["applied_count"] == 0
    assert result["skipped_count"] == 0
    assert result["failed_count"] == 1
    assert result["results"] == [
        {
            "outcome": "failed",
            "status": "HTTP_400",
            "campaign_id": "cmp-1",
            "requested_daily_budget": 25.0,
            "previous_daily_budget": 20.0,
            "error": "Campaign is archived",
        }
    ]
