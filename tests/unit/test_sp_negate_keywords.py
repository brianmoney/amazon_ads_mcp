import importlib
from types import SimpleNamespace

import pytest


negate_module = importlib.import_module("amazon_ads_mcp.tools.sp.negate_keywords")


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
        if path == "/sp/negativeKeywords/list":
            return FakeResponse(
                {
                    "negativeKeywords": [
                        {
                            "negativeKeywordId": "neg-1",
                            "keywordText": "cheap shoes",
                            "matchType": "NEGATIVE_EXACT",
                        }
                    ]
                }
            )
        if path == "/sp/negativeKeywords":
            return FakeResponse(
                {
                    "negativeKeywords": [
                        {
                            "negativeKeywordId": "neg-2",
                            "keywordText": "free shoes",
                            "code": "CREATED",
                        },
                        {
                            "keywordText": "broken shoes",
                            "code": "INVALID_ARGUMENT",
                            "description": "Keyword too long",
                        },
                    ]
                }
            )
        raise AssertionError(f"Unexpected path {path}")


@pytest.mark.asyncio
async def test_negate_keywords_returns_applied_skipped_and_failed_results(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    async def fake_context():
        return manager, "profile-1", "eu", fake_client

    monkeypatch.setattr(
        negate_module,
        "get_sp_write_context",
        fake_context,
    )

    result = await negate_module.negate_keywords(
        campaign_id="cmp-1",
        ad_group_id="ag-1",
        keywords=["cheap shoes", "free shoes", "broken shoes"],
    )

    assert result["skipped_count"] == 1
    assert result["applied_count"] == 1
    assert result["failed_count"] == 1
    skipped = next(item for item in result["results"] if item["outcome"] == "skipped")
    assert skipped["status"] == "ALREADY_NEGATED"
    applied = next(item for item in result["results"] if item["outcome"] == "applied")
    assert applied["negative_keyword_id"] == "neg-2"
    failed = next(item for item in result["results"] if item["outcome"] == "failed")
    assert failed["error"] == "Keyword too long"
