import importlib

import httpx
import pytest

from amazon_ads_mcp.tools.portfolio.common import (
    PortfolioContextError,
    PortfolioValidationError,
    normalize_budget_period,
)


update_budget_module = importlib.import_module(
    "amazon_ads_mcp.tools.portfolio.update_portfolio_budget"
)


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.request = httpx.Request("PUT", "https://example.com/portfolios")

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
            {
                "portfolios": {
                    "success": [
                        {
                            "index": 0,
                            "portfolio": {
                                "portfolioId": "pt-1",
                                "budget": {
                                    "amount": 25.0,
                                    "currencyCode": "USD",
                                    "policy": "DAILY",
                                },
                            },
                        }
                    ]
                }
            },
            status_code=207,
        )

    async def post(self, path, json=None, headers=None):
        self.post_calls.append((path, json, headers))
        assert path == "/portfolios/list"
        return FakeResponse(self.list_payload)

    async def put(self, path, json=None, headers=None):
        self.put_calls.append((path, json, headers))
        assert path == "/portfolios"
        return self.put_response


@pytest.mark.asyncio
async def test_update_portfolio_budget_returns_applied_monthly_result(monkeypatch):
    fake_client = FakeClient(
        list_payload={
            "portfolios": [
                {
                    "portfolioId": "pt-1",
                    "name": "Portfolio A",
                    "state": "ENABLED",
                    "budget": {
                        "amount": 300.0,
                        "currencyCode": "USD",
                        "policy": "DATE_RANGE",
                        "startDate": "2026-01-01",
                        "endDate": "2026-01-31",
                    },
                }
            ]
        },
        put_response=FakeResponse(
            {
                "portfolios": {
                    "success": [
                        {
                            "index": 0,
                            "portfolio": {
                                "portfolioId": "pt-1",
                                "name": "Portfolio A",
                                "state": "ENABLED",
                                "budget": {
                                    "amount": 400.0,
                                    "currencyCode": "USD",
                                    "policy": "DATE_RANGE",
                                    "startDate": "2026-02-01",
                                    "endDate": "2026-02-28",
                                },
                            },
                        }
                    ]
                }
            },
            status_code=207,
        ),
    )

    monkeypatch.setattr(
        update_budget_module,
        "require_portfolio_context",
        lambda: (object(), "profile-1", "na"),
    )
    monkeypatch.setattr(
        update_budget_module,
        "get_portfolio_client",
        pytest.importorskip("unittest.mock").AsyncMock(return_value=fake_client),
    )

    result = await update_budget_module.update_portfolio_budget(
        "pt-1",
        "monthly",
        400.0,
        start_date="2026-02-01",
        end_date="2026-02-28",
    )

    assert result["applied_count"] == 1
    assert result["skipped_count"] == 0
    assert result["failed_count"] == 0
    assert result["results"] == [
        {
            "outcome": "applied",
            "status": "UPDATED",
            "portfolio_id": "pt-1",
            "requested_budget_scope": "monthly",
            "requested_budget_amount": 400.0,
            "requested_budget_start_date": "2026-02-01",
            "requested_budget_end_date": "2026-02-28",
            "currency_code": "USD",
            "previous_budget_policy": "DATE_RANGE",
            "previous_monthly_budget": 300.0,
            "previous_budget_start_date": "2026-01-01",
            "previous_budget_end_date": "2026-01-31",
            "resulting_budget_policy": "DATE_RANGE",
            "resulting_monthly_budget": 400.0,
            "resulting_budget_start_date": "2026-02-01",
            "resulting_budget_end_date": "2026-02-28",
        }
    ]
    assert fake_client.put_calls[0][1] == {
        "portfolios": [
            {
                "portfolioId": "pt-1",
                "budget": {
                    "amount": 400.0,
                    "currencyCode": "USD",
                    "policy": "DATE_RANGE",
                    "startDate": "2026-02-01",
                    "endDate": "2026-02-28",
                },
            }
        ]
    }
    assert fake_client.put_calls[0][2] == {
        "Content-Type": "application/vnd.spPortfolio.v3+json",
        "Accept": "application/vnd.spPortfolio.v3+json",
        "Prefer": "return=representation",
    }


@pytest.mark.asyncio
async def test_update_portfolio_budget_skips_noop_requests(monkeypatch):
    fake_client = FakeClient(
        list_payload={
            "portfolios": [
                {
                    "portfolioId": "pt-1",
                    "budget": {
                        "amount": 25.0,
                        "currencyCode": "USD",
                        "policy": "DAILY",
                    },
                }
            ]
        }
    )

    monkeypatch.setattr(
        update_budget_module,
        "require_portfolio_context",
        lambda: (object(), "profile-1", "eu"),
    )
    monkeypatch.setattr(
        update_budget_module,
        "get_portfolio_client",
        pytest.importorskip("unittest.mock").AsyncMock(return_value=fake_client),
    )

    result = await update_budget_module.update_portfolio_budget(
        "pt-1",
        "daily",
        25.0,
    )

    assert result["applied_count"] == 0
    assert result["skipped_count"] == 1
    assert result["failed_count"] == 0
    assert result["results"] == [
        {
            "outcome": "skipped",
            "status": "ALREADY_SET",
            "portfolio_id": "pt-1",
            "requested_budget_scope": "daily",
            "requested_budget_amount": 25.0,
            "currency_code": "USD",
            "previous_budget_policy": "DAILY",
            "previous_daily_budget": 25.0,
            "resulting_budget_policy": "DAILY",
            "resulting_daily_budget": 25.0,
        }
    ]
    assert fake_client.put_calls == []


@pytest.mark.asyncio
async def test_update_portfolio_budget_returns_failed_result_for_api_rejection(
    monkeypatch,
):
    fake_client = FakeClient(
        list_payload={
            "portfolios": [
                {
                    "portfolioId": "pt-1",
                    "budget": {
                        "amount": 20.0,
                        "currencyCode": "USD",
                        "policy": "DAILY",
                    },
                }
            ]
        },
        put_response=FakeResponse(
            {
                "portfolios": {
                    "error": [
                        {
                            "index": 0,
                            "errors": [
                                {
                                    "errorType": "BUDGET_ERROR",
                                    "errorValue": {
                                        "budgetError": {
                                            "message": "Budget too high",
                                            "reason": "BUDGETING_POLICY_INVALID",
                                        }
                                    },
                                }
                            ],
                        }
                    ]
                }
            },
            status_code=207,
        ),
    )

    monkeypatch.setattr(
        update_budget_module,
        "require_portfolio_context",
        lambda: (object(), "profile-1", "na"),
    )
    monkeypatch.setattr(
        update_budget_module,
        "get_portfolio_client",
        pytest.importorskip("unittest.mock").AsyncMock(return_value=fake_client),
    )

    result = await update_budget_module.update_portfolio_budget(
        "pt-1",
        "daily",
        30.0,
    )

    assert result["applied_count"] == 0
    assert result["skipped_count"] == 0
    assert result["failed_count"] == 1
    assert result["results"] == [
        {
            "outcome": "failed",
            "status": "BUDGET_ERROR",
            "portfolio_id": "pt-1",
            "requested_budget_scope": "daily",
            "requested_budget_amount": 30.0,
            "currency_code": "USD",
            "previous_budget_policy": "DAILY",
            "previous_daily_budget": 20.0,
            "error": "Budget too high",
        }
    ]


@pytest.mark.asyncio
async def test_update_portfolio_budget_surfaces_missing_context(monkeypatch):
    monkeypatch.setattr(
        update_budget_module,
        "require_portfolio_context",
        lambda: (_ for _ in ()).throw(PortfolioContextError("missing profile")),
    )

    with pytest.raises(PortfolioContextError, match="missing profile"):
        await update_budget_module.update_portfolio_budget(
            "pt-1",
            "daily",
            25.0,
        )


def test_normalize_budget_period_rejects_monthly_budget_without_start_date():
    with pytest.raises(
        PortfolioValidationError,
        match="monthly budgets require both start_date and end_date",
    ):
        normalize_budget_period(
            budget_scope="monthly",
            start_date=None,
            end_date="2026-01-31",
        )


def test_normalize_budget_period_rejects_monthly_budget_without_end_date():
    with pytest.raises(
        PortfolioValidationError,
        match="monthly budgets require both start_date and end_date",
    ):
        normalize_budget_period(
            budget_scope="monthly",
            start_date="2026-01-01",
            end_date=None,
        )


def test_normalize_budget_period_rejects_inverted_monthly_dates():
    with pytest.raises(
        PortfolioValidationError,
        match="start_date must be on or before end_date",
    ):
        normalize_budget_period(
            budget_scope="monthly",
            start_date="2026-01-31",
            end_date="2026-01-01",
        )


def test_normalize_budget_period_rejects_daily_budget_dates():
    with pytest.raises(
        PortfolioValidationError,
        match="start_date and end_date are only supported for monthly budgets",
    ):
        normalize_budget_period(
            budget_scope="daily",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
