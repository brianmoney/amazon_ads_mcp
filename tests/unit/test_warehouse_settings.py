from datetime import date

import pytest

from amazon_ads_mcp.config.settings import Settings
from amazon_ads_mcp.warehouse.utils import report_window


@pytest.mark.unit
def test_warehouse_settings_parse_csv_lists(monkeypatch):
    monkeypatch.setenv("WAREHOUSE_PROFILE_IDS", "123, 456 ,,789")
    monkeypatch.setenv("WAREHOUSE_REGIONS", "NA,eu")

    settings = Settings()

    assert settings.warehouse_profile_ids == ["123", "456", "789"]
    assert settings.warehouse_regions == ["na", "eu"]


@pytest.mark.unit
def test_warehouse_regions_must_be_supported(monkeypatch):
    monkeypatch.setenv("WAREHOUSE_REGIONS", "na,moon")

    with pytest.raises(ValueError):
        Settings()


@pytest.mark.unit
def test_effective_warehouse_regions_fall_back_to_default_region(monkeypatch):
    monkeypatch.setenv("WAREHOUSE_REGIONS", "")
    monkeypatch.setenv("AMAZON_ADS_REGION", "fe")

    settings = Settings()

    assert settings.effective_warehouse_regions == ["fe"]


@pytest.mark.unit
def test_warehouse_report_poll_timeout_defaults_to_longer_worker_window(
    monkeypatch,
):
    monkeypatch.delenv("WAREHOUSE_REPORT_POLL_TIMEOUT_SECONDS", raising=False)

    settings = Settings()

    assert settings.warehouse_report_poll_timeout_seconds == 360.0


@pytest.mark.unit
def test_report_window_applies_configured_lag():
    window_start, window_end = report_window(
        settings=Settings.model_construct(
            warehouse_report_window_days=3,
            warehouse_report_lag_days=2,
        ),
        now=date(2026, 4, 28),
    )

    assert window_start.isoformat() == "2026-04-24"
    assert window_end.isoformat() == "2026-04-26"
