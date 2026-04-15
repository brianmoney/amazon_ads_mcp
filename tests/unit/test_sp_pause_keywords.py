import importlib
from types import SimpleNamespace

import pytest


pause_module = importlib.import_module("amazon_ads_mcp.tools.sp.pause_keywords")


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
                    {"keywordId": "kw-1", "keywordText": "shoes", "state": "ENABLED"},
                    {"keywordId": "kw-2", "keywordText": "boots", "state": "PAUSED"},
                    {"keywordId": "kw-3", "keywordText": "sandals", "state": "ENABLED"},
                ]
            }
        )

    async def put(self, path, json=None, headers=None):
        self.put_calls.append((path, json, headers))
        assert path == "/sp/keywords"
        return FakeResponse(
            {
                "keywords": [
                    {"keywordId": "kw-1", "code": "SUCCESS", "state": "PAUSED"},
                    {
                        "keywordId": "kw-3",
                        "code": "INVALID_ARGUMENT",
                        "description": "Keyword is archived",
                    },
                ]
            }
        )


@pytest.mark.asyncio
async def test_pause_keywords_returns_applied_skipped_and_failed_results(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    async def fake_context():
        return manager, "profile-1", "na", fake_client

    monkeypatch.setattr(
        pause_module,
        "get_sp_write_context",
        fake_context,
    )

    result = await pause_module.pause_keywords(
        ["kw-1", "kw-2", "kw-3", "kw-4"],
        reason="trim spend",
    )

    assert result["applied_count"] == 1
    assert result["skipped_count"] == 1
    assert result["failed_count"] == 2
    skipped = next(item for item in result["results"] if item["keyword_id"] == "kw-2")
    assert skipped["status"] == "ALREADY_PAUSED"
    applied = next(item for item in result["results"] if item["keyword_id"] == "kw-1")
    assert applied["resulting_state"] == "PAUSED"
    failed = next(item for item in result["results"] if item["keyword_id"] == "kw-3")
    assert failed["error"] == "Keyword is archived"
    missing = next(item for item in result["results"] if item["keyword_id"] == "kw-4")
    assert missing["status"] == "NOT_FOUND"
