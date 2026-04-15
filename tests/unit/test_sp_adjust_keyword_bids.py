import importlib
from types import SimpleNamespace

import pytest

from amazon_ads_mcp.tools.sp.common import SPContextError


bid_module = importlib.import_module("amazon_ads_mcp.tools.sp.adjust_keyword_bids")


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self):
        self.post_calls = []
        self.put_calls = []

    async def post(self, path, json=None, headers=None):
        self.post_calls.append((path, json, headers))
        assert path == "/sp/keywords/list"
        return FakeResponse(
            {
                "keywords": [
                    {"keywordId": "kw-1", "keywordText": "shoes", "bid": 1.25},
                    {"keywordId": "kw-2", "keywordText": "boots", "bid": 2.0},
                ]
            }
        )

    async def put(self, path, json=None, headers=None):
        self.put_calls.append((path, json, headers))
        assert path == "/sp/keywords"
        return FakeResponse(
            {
                "keywords": [
                    {"keywordId": "kw-1", "code": "SUCCESS", "bid": 1.5},
                    {
                        "keywordId": "kw-2",
                        "code": "INVALID_ARGUMENT",
                        "description": "Bid below placement minimum",
                    },
                ]
            }
        )


@pytest.mark.asyncio
async def test_adjust_keyword_bids_returns_auditable_mixed_results(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    async def fake_context():
        return manager, "profile-1", "na", fake_client

    monkeypatch.setattr(
        bid_module,
        "get_sp_write_context",
        fake_context,
    )

    result = await bid_module.adjust_keyword_bids(
        [
            {"keyword_id": "kw-1", "new_bid": 1.5, "reason": "raise winner"},
            {"keyword_id": "kw-2", "new_bid": 0.5},
            {"keyword_id": "kw-3", "new_bid": 0.9},
        ]
    )

    assert result["applied_count"] == 1
    assert result["failed_count"] == 2
    assert result["results"][0] == {
        "outcome": "failed",
        "status": "NOT_FOUND",
        "keyword_id": "kw-3",
        "requested_bid": 0.9,
        "error": "Keyword was not found during preflight lookup",
    }
    applied = next(item for item in result["results"] if item["keyword_id"] == "kw-1")
    assert applied["previous_bid"] == 1.25
    assert applied["resulting_bid"] == 1.5
    assert applied["reason"] == "raise winner"
    failed = next(item for item in result["results"] if item["keyword_id"] == "kw-2")
    assert failed["status"] == "INVALID_ARGUMENT"
    assert failed["error"] == "Bid below placement minimum"


@pytest.mark.asyncio
async def test_adjust_keyword_bids_surfaces_missing_context(monkeypatch):
    async def fake_context():
        raise SPContextError("missing profile")

    monkeypatch.setattr(
        bid_module,
        "get_sp_write_context",
        fake_context,
    )

    with pytest.raises(SPContextError, match="missing profile"):
        await bid_module.adjust_keyword_bids([{"keyword_id": "kw-1", "new_bid": 1.5}])
