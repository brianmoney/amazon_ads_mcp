from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.sp import report_status as status_module
from amazon_ads_mcp.tools.sp.report_helper import SPReportError


@pytest.mark.asyncio
async def test_get_sp_report_status_returns_in_progress_status(monkeypatch):
    manager = SimpleNamespace()
    fake_client = object()

    monkeypatch.setattr(
        status_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        status_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        status_module,
        "fetch_sp_report_status",
        AsyncMock(
            return_value={
                "report_id": "rpt-1",
                "status": "PROCESSING",
                "raw_status": "IN_PROGRESS",
                "status_details": None,
                "download_url": None,
                "generated_at": None,
                "updated_at": None,
                "url_expires_at": None,
            }
        ),
    )

    result = await status_module.get_sp_report_status("rpt-1")

    assert result["report_id"] == "rpt-1"
    assert result["status"] == "PROCESSING"
    assert result["profile_id"] == "profile-1"
    assert result["region"] == "na"


@pytest.mark.asyncio
async def test_get_sp_report_status_returns_completed_status(monkeypatch):
    manager = SimpleNamespace()
    fake_client = object()

    monkeypatch.setattr(
        status_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        status_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        status_module,
        "fetch_sp_report_status",
        AsyncMock(
            return_value={
                "report_id": "rpt-2",
                "status": "COMPLETED",
                "raw_status": "SUCCESS",
                "status_details": None,
                "download_url": "https://download.example/report.gz",
                "generated_at": "2026-01-01T00:00:00Z",
                "updated_at": None,
                "url_expires_at": None,
            }
        ),
    )

    result = await status_module.get_sp_report_status("rpt-2")

    assert result["status"] == "COMPLETED"
    assert result["download_url"] == "https://download.example/report.gz"


@pytest.mark.asyncio
async def test_get_sp_report_status_returns_failed_status(monkeypatch):
    manager = SimpleNamespace()
    fake_client = object()

    monkeypatch.setattr(
        status_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        status_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        status_module,
        "fetch_sp_report_status",
        AsyncMock(
            return_value={
                "report_id": "rpt-3",
                "status": "FAILED",
                "raw_status": "FAILED",
                "status_details": "invalid columns",
                "download_url": None,
                "generated_at": None,
                "updated_at": None,
                "url_expires_at": None,
            }
        ),
    )

    result = await status_module.get_sp_report_status("rpt-3")

    assert result["status"] == "FAILED"
    assert result["status_details"] == "invalid columns"


@pytest.mark.asyncio
async def test_get_sp_report_status_surfaces_lookup_errors(monkeypatch):
    manager = SimpleNamespace()
    fake_client = object()

    monkeypatch.setattr(
        status_module, "require_sp_context", lambda: (manager, "profile-1", "na")
    )
    monkeypatch.setattr(
        status_module, "get_sp_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        status_module,
        "fetch_sp_report_status",
        AsyncMock(side_effect=SPReportError("status lookup failed")),
    )

    with pytest.raises(SPReportError, match="status lookup failed"):
        await status_module.get_sp_report_status("rpt-4")
