from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from amazon_ads_mcp.tools.sd import report_status as status_module
from amazon_ads_mcp.tools.sd.report_helper import SDReportError


@pytest.mark.asyncio
async def test_get_sd_report_status_returns_queued_status(monkeypatch):
    manager = SimpleNamespace()
    fake_client = object()

    monkeypatch.setattr(
        status_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        status_module, "get_sd_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        status_module,
        "fetch_sd_report_status",
        AsyncMock(
            return_value={
                "report_id": "sd-rpt-1",
                "status": "QUEUED",
                "raw_status": "PENDING",
                "status_details": None,
                "download_url": None,
                "generated_at": None,
                "updated_at": "2026-01-01T00:00:00Z",
                "url_expires_at": None,
            }
        ),
    )

    result = await status_module.get_sd_report_status("sd-rpt-1")

    assert result["report_id"] == "sd-rpt-1"
    assert result["status"] == "QUEUED"
    assert result["raw_status"] == "PENDING"
    assert result["resume_from_report_id"] is None
    assert result["profile_id"] == "profile-1"
    assert result["region"] == "eu"


@pytest.mark.asyncio
async def test_get_sd_report_status_returns_processing_status(monkeypatch):
    manager = SimpleNamespace()
    fake_client = object()

    monkeypatch.setattr(
        status_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        status_module, "get_sd_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        status_module,
        "fetch_sd_report_status",
        AsyncMock(
            return_value={
                "report_id": "sd-rpt-2",
                "status": "PROCESSING",
                "raw_status": "IN_PROGRESS",
                "status_details": "still running",
                "download_url": None,
                "generated_at": None,
                "updated_at": "2026-01-01T00:00:00Z",
                "url_expires_at": None,
            }
        ),
    )

    result = await status_module.get_sd_report_status("sd-rpt-2")

    assert result["status"] == "PROCESSING"
    assert result["status_details"] == "still running"
    assert result["resume_from_report_id"] is None


@pytest.mark.asyncio
async def test_get_sd_report_status_returns_completed_resume_details(monkeypatch):
    manager = SimpleNamespace()
    fake_client = object()

    monkeypatch.setattr(
        status_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        status_module, "get_sd_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        status_module,
        "fetch_sd_report_status",
        AsyncMock(
            return_value={
                "report_id": "sd-rpt-3",
                "status": "COMPLETED",
                "raw_status": "SUCCESS",
                "status_details": None,
                "download_url": "https://download.example/report.gz",
                "generated_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:05:00Z",
                "url_expires_at": "2026-01-01T01:00:00Z",
            }
        ),
    )

    result = await status_module.get_sd_report_status("sd-rpt-3")

    assert result["status"] == "COMPLETED"
    assert result["download_url"] == "https://download.example/report.gz"
    assert result["resume_from_report_id"] == "sd-rpt-3"


@pytest.mark.asyncio
async def test_get_sd_report_status_returns_terminal_failure(monkeypatch):
    manager = SimpleNamespace()
    fake_client = object()

    monkeypatch.setattr(
        status_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        status_module, "get_sd_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        status_module,
        "fetch_sd_report_status",
        AsyncMock(
            return_value={
                "report_id": "sd-rpt-4",
                "status": "FAILED",
                "raw_status": "ERROR",
                "status_details": "invalid report columns",
                "download_url": None,
                "generated_at": None,
                "updated_at": "2026-01-01T00:05:00Z",
                "url_expires_at": None,
            }
        ),
    )

    result = await status_module.get_sd_report_status("sd-rpt-4")

    assert result["status"] == "FAILED"
    assert result["status_details"] == "invalid report columns"
    assert result["resume_from_report_id"] is None


@pytest.mark.asyncio
async def test_get_sd_report_status_returns_cancelled_status(monkeypatch):
    manager = SimpleNamespace()
    fake_client = object()

    monkeypatch.setattr(
        status_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        status_module, "get_sd_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        status_module,
        "fetch_sd_report_status",
        AsyncMock(
            return_value={
                "report_id": "sd-rpt-5",
                "status": "CANCELLED",
                "raw_status": "CANCELED",
                "status_details": "cancelled upstream",
                "download_url": None,
                "generated_at": None,
                "updated_at": "2026-01-01T00:04:00Z",
                "url_expires_at": None,
            }
        ),
    )

    result = await status_module.get_sd_report_status("sd-rpt-5")

    assert result["status"] == "CANCELLED"
    assert result["status_details"] == "cancelled upstream"


@pytest.mark.asyncio
async def test_get_sd_report_status_surfaces_lookup_errors(monkeypatch):
    manager = SimpleNamespace()
    fake_client = object()

    monkeypatch.setattr(
        status_module, "require_sd_context", lambda: (manager, "profile-1", "eu")
    )
    monkeypatch.setattr(
        status_module, "get_sd_client", AsyncMock(return_value=fake_client)
    )
    monkeypatch.setattr(
        status_module,
        "fetch_sd_report_status",
        AsyncMock(side_effect=SDReportError("status lookup failed")),
    )

    with pytest.raises(SDReportError, match="status lookup failed"):
        await status_module.get_sd_report_status("sd-rpt-6")
