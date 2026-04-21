from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.sp import search_term_report as search_term_module
from amazon_ads_mcp.tools.sp.report_helper import SPReportError


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

    async def post(self, path, json=None):
        self.calls.append((path, json))
        if path == "/sp/targets/list":
            return FakeResponse(
                {"targets": [{"targetId": 1, "keywordText": "running shoes"}]}
            )
        if path == "/sp/negativeTargets/list":
            return FakeResponse(
                {
                    "negativeTargets": [
                        {
                            "targetId": 2,
                            "keywordText": "cheap shoes",
                            "matchType": "NEGATIVE_PHRASE",
                        }
                    ]
                }
            )
        raise AssertionError(f"Unexpected path {path}")


@pytest.mark.asyncio
async def test_get_search_term_report_adds_targeting_annotations(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        search_term_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        search_term_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        search_term_module,
        "run_sp_report",
        AsyncMock(
            return_value={
                "report_id": "rpt-3",
                "rows": [
                    {
                        "campaignId": 10,
                        "searchTerm": "Running Shoes",
                        "clicks": 5,
                        "cost": 12,
                    },
                    {
                        "campaignId": 10,
                        "searchTerm": "cheap shoes",
                        "clicks": 2,
                        "cost": 4,
                    },
                ],
            }
        ),
    )

    result = await search_term_module.get_search_term_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    first, second = result["rows"]
    assert first["manually_targeted"] is True
    assert first["negated"] is False
    assert second["manually_targeted"] is False
    assert second["negated"] is True
    assert second["negative_match_types"] == ["NEGATIVE_PHRASE"]


@pytest.mark.asyncio
async def test_get_search_term_report_surfaces_report_failures(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        search_term_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        search_term_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        search_term_module,
        "run_sp_report",
        AsyncMock(side_effect=SPReportError("download failed")),
    )

    with pytest.raises(SPReportError, match="download failed"):
        await search_term_module.get_search_term_report(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )


@pytest.mark.asyncio
async def test_get_search_term_report_uses_safer_default_timeout(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()
    run_report = AsyncMock(return_value={"report_id": "rpt-timeout", "rows": []})

    monkeypatch.setattr(
        search_term_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        search_term_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(search_term_module, "run_sp_report", run_report)

    await search_term_module.get_search_term_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    assert run_report.await_args.kwargs["timeout_seconds"] == 120.0


@pytest.mark.asyncio
async def test_get_search_term_report_resumes_completed_report(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()
    run_report = AsyncMock()
    resume_report = AsyncMock(
        return_value={
            "report_id": "rpt-resume",
            "rows": [{"campaignId": 10, "searchTerm": "running shoes"}],
        }
    )

    monkeypatch.setattr(
        search_term_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        search_term_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(search_term_module, "run_sp_report", run_report)
    monkeypatch.setattr(search_term_module, "resume_sp_report", resume_report)

    result = await search_term_module.get_search_term_report(
        start_date="2026-01-01",
        end_date="2026-01-31",
        resume_from_report_id="rpt-resume",
    )

    assert result["report_id"] == "rpt-resume"
    assert result["filters"]["resume_from_report_id"] == "rpt-resume"
    run_report.assert_not_called()
    resume_report.assert_awaited_once_with("rpt-resume", client=fake_client)


@pytest.mark.asyncio
async def test_get_search_term_report_surfaces_non_ready_resume(monkeypatch):
    fake_client = FakeClient()
    manager = SimpleNamespace()

    monkeypatch.setattr(
        search_term_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        search_term_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(search_term_module, "resume_sp_report", AsyncMock(side_effect=SPReportError("not ready (status: PROCESSING)")))

    with pytest.raises(SPReportError, match="PROCESSING"):
        await search_term_module.get_search_term_report(
            start_date="2026-01-01",
            end_date="2026-01-31",
            resume_from_report_id="rpt-pending",
        )
