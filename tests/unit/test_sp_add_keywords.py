import importlib
from types import SimpleNamespace

import pytest


add_module = importlib.import_module("amazon_ads_mcp.tools.sp.add_keywords")


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

    async def post(self, path, json=None, headers=None):
        self.post_calls.append((path, json, headers))
        if path == "/sp/keywords/list":
            return FakeResponse(
                {
                    "keywords": [
                        {
                            "keywordId": "existing-1",
                            "keywordText": "running shoes",
                            "matchType": "EXACT",
                            "bid": 1.1,
                            "state": "ENABLED",
                        }
                    ]
                }
            )
        if path == "/sp/keywords":
            return FakeResponse(
                {
                    "keywords": [
                        {
                            "keywordId": "new-1",
                            "keywordText": "trail shoes",
                            "matchType": "PHRASE",
                            "code": "CREATED",
                        },
                        {
                            "keywordText": "dress shoes",
                            "matchType": "EXACT",
                            "code": "INVALID_ARGUMENT",
                            "description": "Bid exceeds campaign cap",
                        },
                    ]
                }
            )
        raise AssertionError(f"Unexpected path {path}")


@pytest.mark.asyncio
async def test_add_keywords_returns_applied_skipped_and_failed_results(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    async def fake_context():
        return manager, "profile-1", "na", fake_client

    monkeypatch.setattr(
        add_module,
        "get_sp_write_context",
        fake_context,
    )

    result = await add_module.add_keywords(
        campaign_id="cmp-1",
        ad_group_id="ag-1",
        keywords=[
            {"keyword_text": "running shoes", "bid": 1.0},
            {"keyword_text": "trail shoes", "match_type": "PHRASE", "bid": 1.3},
            {"keyword_text": "dress shoes", "bid": 1.9},
        ],
    )

    assert result["skipped_count"] == 1
    assert result["applied_count"] == 1
    assert result["failed_count"] == 1
    skipped = next(item for item in result["results"] if item["outcome"] == "skipped")
    assert skipped["existing_keyword_id"] == "existing-1"
    applied = next(item for item in result["results"] if item["outcome"] == "applied")
    assert applied["keyword_id"] == "new-1"
    failed = next(item for item in result["results"] if item["outcome"] == "failed")
    assert failed["error"] == "Bid exceeds campaign cap"
