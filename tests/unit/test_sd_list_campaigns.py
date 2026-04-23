import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.sd.common import SDContextError


list_campaigns_module = importlib.import_module(
    "amazon_ads_mcp.tools.sd.list_campaigns"
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
        if path == "/adsApi/v1/query/campaigns":
            return FakeResponse(
                {
                    "campaigns": [
                        {
                            "campaignId": 10,
                            "name": "Retargeting",
                            "state": "ENABLED",
                            "budgets": [
                                {
                                    "budgetType": "MONETARY",
                                    "budgetValue": {
                                        "monetaryBudgetValue": {
                                            "monetaryBudget": {"value": 40}
                                        }
                                    },
                                    "recurrenceTimePeriod": "DAILY",
                                }
                            ],
                            "campaignObjective": "CONVERSIONS",
                            "costType": "CPC",
                        },
                        {
                            "campaignId": 11,
                            "name": "Reach",
                            "state": "PAUSED",
                            "budgets": [
                                {
                                    "budgetType": "MONETARY",
                                    "budgetValue": {
                                        "monetaryBudgetValue": {
                                            "monetaryBudget": {"value": 15}
                                        }
                                    },
                                    "recurrenceTimePeriod": "DAILY",
                                }
                            ],
                            "campaignObjective": "REACH",
                            "costType": "VCPM",
                        },
                    ]
                }
            )
        if path == "/adsApi/v1/query/adGroups":
            return FakeResponse(
                {
                    "adGroups": [
                        {
                            "campaignId": 10,
                            "adGroupId": 100,
                            "name": "Viewed PDP",
                            "state": "ENABLED",
                        },
                        {
                            "campaignId": 11,
                            "name": "Audience only",
                            "state": "PAUSED",
                        },
                    ]
                }
            )
        raise AssertionError(f"Unexpected path {path}")


@pytest.mark.asyncio
async def test_list_sd_campaigns_returns_campaigns_with_targeting_groups(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        list_campaigns_module,
        "require_sd_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        list_campaigns_module, "get_sd_client", AsyncMock(return_value=fake_client)
    )

    result = await list_campaigns_module.list_sd_campaigns(
        campaign_states=["enabled"],
        campaign_ids=["10", "11"],
        limit=2,
        offset=0,
    )

    assert result["profile_id"] == "profile-1"
    assert result["region"] == "na"
    assert result["returned_count"] == 2
    assert result["campaigns"][0]["campaign_id"] == "10"
    assert result["campaigns"][0]["objective"] == "CONVERSIONS"
    assert result["campaigns"][0]["bidding_model"] == "CPC"
    assert result["campaigns"][0]["targeting_groups"] == [
        {
            "targeting_group_id": "100",
            "targeting_group_name": "Viewed PDP",
            "state": "ENABLED",
        }
    ]
    assert result["campaigns"][1]["targeting_groups"] == [
        {
            "targeting_group_id": None,
            "targeting_group_name": "Audience only",
            "state": "PAUSED",
        }
    ]
    assert fake_client.calls[0][1] == {
        "adProductFilter": {"include": ["SPONSORED_DISPLAY"]},
        "maxResults": 2,
        "stateFilter": {"include": ["ENABLED"]},
        "campaignIdFilter": {"include": ["10", "11"]},
    }
    assert fake_client.calls[0][2] == {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    assert fake_client.calls[1][1] == {
        "adProductFilter": {"include": ["SPONSORED_DISPLAY"]},
        "campaignIdFilter": {"include": ["10", "11"]},
        "maxResults": 40,
    }
    assert fake_client.calls[1][2] == {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@pytest.mark.asyncio
async def test_list_sd_campaigns_filters_objectives_after_live_query_contract(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        list_campaigns_module,
        "require_sd_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        list_campaigns_module, "get_sd_client", AsyncMock(return_value=fake_client)
    )

    result = await list_campaigns_module.list_sd_campaigns(
        objectives=["conversions"],
        limit=25,
    )

    assert [campaign["campaign_id"] for campaign in result["campaigns"]] == ["10"]


@pytest.mark.asyncio
async def test_list_sd_campaigns_requires_active_context(monkeypatch):
    monkeypatch.setattr(
        list_campaigns_module,
        "require_sd_context",
        lambda: (_ for _ in ()).throw(SDContextError("missing profile")),
    )

    with pytest.raises(SDContextError, match="missing profile"):
        await list_campaigns_module.list_sd_campaigns()
