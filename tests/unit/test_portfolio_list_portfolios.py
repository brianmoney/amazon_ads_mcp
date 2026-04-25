import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.portfolio.common import PortfolioContextError


list_portfolios_module = importlib.import_module(
    "amazon_ads_mcp.tools.portfolio.list_portfolios"
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class PagingClient:
    def __init__(self):
        self.calls = []

    async def post(self, path, json=None, headers=None):
        self.calls.append((path, json, headers))
        assert path == "/portfolios/list"

        if len(self.calls) == 1:
            return FakeResponse(
                {
                    "nextToken": "page-2",
                    "totalResults": 2,
                    "portfolios": [
                        {
                            "portfolioId": "pt-1",
                            "name": "Daily Portfolio",
                            "state": "ENABLED",
                            "inBudget": True,
                            "budget": {
                                "amount": 25,
                                "currencyCode": "USD",
                                "policy": "DAILY",
                            },
                        }
                    ],
                }
            )

        return FakeResponse(
            {
                "totalResults": 2,
                "portfolios": [
                    {
                        "portfolioId": "pt-2",
                        "name": "Monthly Portfolio",
                        "state": "PAUSED",
                        "inBudget": False,
                        "budget": {
                            "amount": 300,
                            "currencyCode": "USD",
                            "policy": "DATE_RANGE",
                            "startDate": "2026-01-01",
                            "endDate": "2026-01-31",
                        },
                        "extendedData": {
                            "servingStatus": "PORTFOLIO_PAUSED",
                            "statusReasons": ["CAMPAIGNS_PAUSED"],
                        },
                    }
                ],
            }
        )


class SinglePageClient:
    def __init__(self, payload):
        self.calls = []
        self.payload = payload

    async def post(self, path, json=None, headers=None):
        self.calls.append((path, json, headers))
        assert path == "/portfolios/list"
        return FakeResponse(self.payload)


@pytest.mark.asyncio
async def test_list_portfolios_returns_normalized_budget_context(monkeypatch):
    fake_client = PagingClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        list_portfolios_module,
        "require_portfolio_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        list_portfolios_module,
        "get_portfolio_client",
        AsyncMock(return_value=fake_client),
    )

    result = await list_portfolios_module.list_portfolios(
        portfolio_states=["enabled"],
        portfolio_ids=["pt-1", "pt-2"],
        limit=1,
        offset=1,
    )

    assert result["profile_id"] == "profile-1"
    assert result["region"] == "na"
    assert result["returned_count"] == 1
    assert result["total_results"] == 2
    assert result["filters"] == {
        "portfolio_states": ["ENABLED"],
        "portfolio_ids": ["pt-1", "pt-2"],
        "limit": 1,
        "offset": 1,
    }
    assert result["portfolios"] == [
        {
            "portfolio_id": "pt-2",
            "name": "Monthly Portfolio",
            "state": "PAUSED",
            "in_budget": False,
            "serving_status": "PORTFOLIO_PAUSED",
            "status_reasons": ["CAMPAIGNS_PAUSED"],
            "campaign_unspent_budget_sharing_state": None,
            "budget_policy": "DATE_RANGE",
            "budget_scope": "monthly",
            "cap_amount": 300.0,
            "daily_budget": None,
            "monthly_budget": 300.0,
            "currency_code": "USD",
            "budget_start_date": "2026-01-01",
            "budget_end_date": "2026-01-31",
        }
    ]
    assert fake_client.calls[0][1] == {
        "includeExtendedDataFields": True,
        "portfolioIdFilter": {"include": ["pt-1", "pt-2"]},
        "stateFilter": {"include": ["ENABLED"]},
    }
    assert fake_client.calls[1][1] == {
        "includeExtendedDataFields": True,
        "portfolioIdFilter": {"include": ["pt-1", "pt-2"]},
        "stateFilter": {"include": ["ENABLED"]},
        "nextToken": "page-2",
    }
    assert fake_client.calls[0][2] == {
        "Content-Type": "application/vnd.spPortfolio.v3+json",
        "Accept": "application/vnd.spPortfolio.v3+json",
    }


@pytest.mark.asyncio
async def test_list_portfolios_requires_active_context(monkeypatch):
    monkeypatch.setattr(
        list_portfolios_module,
        "require_portfolio_context",
        lambda: (_ for _ in ()).throw(PortfolioContextError("missing profile")),
    )

    with pytest.raises(PortfolioContextError, match="missing profile"):
        await list_portfolios_module.list_portfolios()


@pytest.mark.asyncio
async def test_list_portfolios_uses_unfiltered_default_request_shape(monkeypatch):
    fake_client = SinglePageClient(
        {
            "totalResults": 1,
            "portfolios": [
                {
                    "portfolioId": "pt-1",
                    "name": "Default Portfolio",
                    "state": "ENABLED",
                    "budget": {
                        "amount": 25,
                        "currencyCode": "USD",
                        "policy": "DAILY",
                    },
                }
            ],
        }
    )
    manager = SimpleNamespace()

    monkeypatch.setattr(
        list_portfolios_module,
        "require_portfolio_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        list_portfolios_module,
        "get_portfolio_client",
        AsyncMock(return_value=fake_client),
    )

    result = await list_portfolios_module.list_portfolios()

    assert result["filters"] == {
        "portfolio_states": [],
        "portfolio_ids": [],
        "limit": 25,
        "offset": 0,
    }
    assert result["returned_count"] == 1
    assert fake_client.calls[0][1] == {"includeExtendedDataFields": True}


@pytest.mark.asyncio
async def test_list_portfolios_normalizes_invalid_bounds(monkeypatch):
    fake_client = SinglePageClient(
        {
            "totalResults": 1,
            "portfolios": [
                {
                    "portfolioId": "pt-1",
                    "name": "Bounded Portfolio",
                    "state": "ENABLED",
                }
            ],
        }
    )
    manager = SimpleNamespace()

    monkeypatch.setattr(
        list_portfolios_module,
        "require_portfolio_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        list_portfolios_module,
        "get_portfolio_client",
        AsyncMock(return_value=fake_client),
    )

    result = await list_portfolios_module.list_portfolios(limit=999, offset=-7)

    assert result["filters"] == {
        "portfolio_states": [],
        "portfolio_ids": [],
        "limit": 100,
        "offset": 0,
    }
    assert fake_client.calls[0][1] == {"includeExtendedDataFields": True}
