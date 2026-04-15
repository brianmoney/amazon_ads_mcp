import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.sp.common import SPContextError


list_campaigns_module = importlib.import_module(
    "amazon_ads_mcp.tools.sp.list_campaigns"
)


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
        if path == "/sp/campaigns/list":
            return FakeResponse(
                {
                    "campaigns": [
                        {
                            "campaignId": 10,
                            "name": "Campaign A",
                            "state": "ENABLED",
                            "budget": 25,
                        },
                        {
                            "campaignId": 11,
                            "name": "Campaign B",
                            "state": "PAUSED",
                            "budget": 15,
                        },
                    ]
                }
            )
        if path == "/sp/adGroups/list":
            return FakeResponse(
                {
                    "adGroups": [
                        {
                            "adGroupId": 100,
                            "campaignId": 10,
                            "name": "A1",
                            "defaultBid": 1.5,
                        },
                        {
                            "adGroupId": 101,
                            "campaignId": 10,
                            "name": "A2",
                            "defaultBid": 2.0,
                        },
                    ]
                }
            )
        raise AssertionError(f"Unexpected path {path}")


@pytest.mark.asyncio
async def test_list_campaigns_returns_campaign_hierarchy(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        list_campaigns_module,
        "require_sp_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        list_campaigns_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )

    result = await list_campaigns_module.list_campaigns(
        campaign_states=["enabled"],
        campaign_ids=["10", "11"],
        limit=2,
        offset=5,
    )

    assert result["profile_id"] == "profile-1"
    assert result["region"] == "na"
    assert result["returned_count"] == 2
    assert result["campaigns"][0]["campaign_id"] == "10"
    assert len(result["campaigns"][0]["ad_groups"]) == 2
    assert result["campaigns"][1]["ad_groups"] == []
    assert fake_client.calls[0][1] == {
        "count": 2,
        "startIndex": 5,
        "stateFilter": ["ENABLED"],
        "campaignIdFilter": ["10", "11"],
    }
    assert fake_client.calls[0][2] == {
        "Content-Type": "application/vnd.spCampaign.v3+json",
        "Accept": "application/vnd.spCampaign.v3+json",
    }
    assert fake_client.calls[1][2] == {
        "Content-Type": "application/vnd.spAdGroup.v3+json",
        "Accept": "application/vnd.spAdGroup.v3+json",
    }
    assert fake_client.calls[1][1] == {
        "campaignIdFilter": {"include": ["10", "11"]},
        "count": 40,
    }


@pytest.mark.asyncio
async def test_list_campaigns_requires_active_context(monkeypatch):
    monkeypatch.setattr(
        list_campaigns_module,
        "require_sp_context",
        lambda: (_ for _ in ()).throw(SPContextError("missing profile")),
    )

    with pytest.raises(SPContextError, match="missing profile"):
        await list_campaigns_module.list_campaigns()
