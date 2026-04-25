import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.portfolio.common import PortfolioContextError


budget_usage_module = importlib.import_module(
    "amazon_ads_mcp.tools.portfolio.budget_usage"
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class BudgetUsageClient:
    def __init__(self, *, list_payload, usage_payload):
        self.calls = []
        self.list_payload = list_payload
        self.usage_payload = usage_payload

    async def post(self, path, json=None, headers=None):
        self.calls.append((path, json, headers))
        if path == "/portfolios/list":
            return FakeResponse(self.list_payload)
        if path == "/portfolios/budget/usage":
            return FakeResponse(self.usage_payload)
        raise AssertionError(f"Unexpected path {path}")


@pytest.mark.asyncio
async def test_get_portfolio_budget_usage_returns_rows_and_partial_diagnostics(
    monkeypatch,
):
    fake_client = BudgetUsageClient(
        list_payload={
            "portfolios": [
                {
                    "portfolioId": "pt-1",
                    "name": "Daily Portfolio",
                    "state": "ENABLED",
                    "budget": {
                        "amount": 100,
                        "currencyCode": "USD",
                        "policy": "DAILY",
                    },
                }
            ]
        },
        usage_payload={
            "success": [
                {
                    "portfolioId": "pt-1",
                    "budget": 100,
                    "budgetUsagePercent": 25,
                    "usageUpdatedTimestamp": "2026-01-10T12:00:00Z",
                }
            ],
            "error": [
                {
                    "portfolioId": "pt-2",
                    "code": "UNAUTHORIZED",
                    "details": "Forbidden",
                    "index": 1,
                }
            ],
        },
    )
    manager = SimpleNamespace()

    monkeypatch.setattr(
        budget_usage_module,
        "require_portfolio_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        budget_usage_module,
        "get_portfolio_client",
        AsyncMock(return_value=fake_client),
    )

    result = await budget_usage_module.get_portfolio_budget_usage(["pt-1", "pt-2"])

    assert result["filters"] == {"portfolio_ids": ["pt-1", "pt-2"]}
    assert result["returned_count"] == 1
    assert result["availability"] == {
        "state": "partial",
        "reason": "Portfolio budget usage data was only partially available for the requested scope.",
        "missing_portfolio_ids": ["pt-2"],
    }
    assert result["rows"] == [
        {
            "portfolio_id": "pt-1",
            "name": "Daily Portfolio",
            "state": "ENABLED",
            "in_budget": None,
            "serving_status": None,
            "status_reasons": [],
            "campaign_unspent_budget_sharing_state": None,
            "budget_policy": "DAILY",
            "budget_scope": "daily",
            "cap_amount": 100.0,
            "daily_budget": 100.0,
            "monthly_budget": None,
            "currency_code": "USD",
            "budget_start_date": None,
            "budget_end_date": None,
            "current_spend": 25.0,
            "remaining_budget": 75.0,
            "utilization_pct": 25.0,
            "usage_updated_timestamp": "2026-01-10T12:00:00Z",
            "availability": {
                "state": "available",
                "reason": None,
                "missing_fields": [],
            },
        }
    ]
    assert result["diagnostics"] == [
        {
            "portfolio_id": "pt-2",
            "state": "unavailable",
            "code": "UNAUTHORIZED",
            "details": "Forbidden",
            "index": 1,
        }
    ]
    assert fake_client.calls[0][1] == {
        "includeExtendedDataFields": True,
        "portfolioIdFilter": {"include": ["pt-1", "pt-2"]},
    }
    assert fake_client.calls[1][1] == {"portfolioIds": ["pt-1", "pt-2"]}


@pytest.mark.asyncio
async def test_get_portfolio_budget_usage_marks_rows_partial_when_settings_missing(
    monkeypatch,
):
    fake_client = BudgetUsageClient(
        list_payload={"portfolios": []},
        usage_payload={
            "success": [
                {
                    "portfolioId": "pt-1",
                    "budget": 80,
                    "budgetUsagePercent": 50,
                    "usageUpdatedTimestamp": "2026-01-10T12:00:00Z",
                }
            ]
        },
    )
    manager = SimpleNamespace()

    monkeypatch.setattr(
        budget_usage_module,
        "require_portfolio_context",
        lambda: (manager, "profile-1", "na"),
    )
    monkeypatch.setattr(
        budget_usage_module,
        "get_portfolio_client",
        AsyncMock(return_value=fake_client),
    )

    result = await budget_usage_module.get_portfolio_budget_usage(["pt-1"])

    assert result["availability"] == {
        "state": "partial",
        "reason": "Portfolio budget usage data was only partially available for the requested scope.",
        "missing_portfolio_ids": [],
    }
    assert result["rows"][0]["availability"] == {
        "state": "partial",
        "reason": (
            "Portfolio settings were unavailable for this portfolio, so only "
            "partial budget-usage context could be returned."
        ),
        "missing_fields": [
            "name",
            "state",
            "budget_policy",
            "budget_scope",
            "currency_code",
            "daily_budget",
            "monthly_budget",
            "budget_start_date",
            "budget_end_date",
        ],
    }


@pytest.mark.asyncio
async def test_get_portfolio_budget_usage_surfaces_missing_context(monkeypatch):
    monkeypatch.setattr(
        budget_usage_module,
        "require_portfolio_context",
        lambda: (_ for _ in ()).throw(PortfolioContextError("missing profile")),
    )

    with pytest.raises(PortfolioContextError, match="missing profile"):
        await budget_usage_module.get_portfolio_budget_usage(["pt-1"])
