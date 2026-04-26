from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine

from amazon_ads_mcp.warehouse.schema import metadata, sp_campaign_budget_history_fact, sp_placement_fact
from amazon_ads_mcp.warehouse.validation import (
    _compare_rows,
    validate_budget_history,
    validate_placement_report,
)


@pytest.fixture
def connection():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata.create_all(engine)
    with engine.begin() as conn:
        yield conn


@pytest.mark.unit
def test_compare_rows_normalizes_order_and_nested_values():
    live_rows = [
        {
            "keyword_id": "2",
            "manual_target_ids": ["b", "a"],
            "metrics": {"clicks": 2, "impressions": 10},
        },
        {
            "keyword_id": "1",
            "manual_target_ids": ["z"],
            "metrics": {"clicks": 1, "impressions": 5},
        },
    ]
    warehouse_rows = [
        {
            "keyword_id": "1",
            "manual_target_ids": ["z"],
            "metrics": {"impressions": 5, "clicks": 1},
        },
        {
            "keyword_id": "2",
            "manual_target_ids": ["a", "b"],
            "metrics": {"impressions": 10, "clicks": 2},
        },
    ]

    result = _compare_rows(live_rows, warehouse_rows)

    assert result["matched"] is True


@pytest.mark.asyncio
async def test_validate_budget_history_projects_warehouse_rows(connection, monkeypatch):
    async def fake_budget_history(*, start_date, end_date, limit):
        assert start_date == "2026-01-01"
        assert end_date == "2026-01-02"
        assert limit == 100
        return {
            "rows": [
                {
                    "date": "2026-01-01",
                    "campaign_id": "10",
                    "campaign_name": "Campaign A",
                    "daily_budget": 100.0,
                    "spend": 75.0,
                    "utilization_pct": 75.0,
                    "hours_ran": 18.0,
                }
            ]
        }

    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.validation.get_campaign_budget_history",
        fake_budget_history,
    )
    connection.execute(
        sp_campaign_budget_history_fact.insert().values(
            profile_id="profile-1",
            campaign_id="10",
            budget_date=date(2026, 1, 1),
            campaign_name="Campaign A",
            daily_budget=100,
            spend=75,
            utilization_pct=75,
            hours_ran=18,
            last_report_run_id="run-1",
            retrieved_at=datetime.now(UTC),
        )
    )

    result = await validate_budget_history(
        connection,
        profile_id="profile-1",
        start_date="2026-01-01",
        end_date="2026-01-02",
    )

    assert result["matched"] is True


@pytest.mark.asyncio
async def test_validate_placement_report_projects_warehouse_rows(connection, monkeypatch):
    async def fake_placement_report(*, start_date, end_date, limit):
        assert start_date == "2026-01-01"
        assert end_date == "2026-01-02"
        assert limit == 100
        return {
            "rows": [
                {
                    "campaign_id": "10",
                    "campaign_name": "Campaign A",
                    "placement_type": "top_of_search",
                    "impressions": 1000.0,
                    "clicks": 50.0,
                    "spend": 25.0,
                    "sales14d": 200.0,
                    "purchases14d": 4.0,
                    "ctr": 0.05,
                    "cpc": 0.5,
                    "acos": 0.125,
                    "roas": 8.0,
                    "current_top_of_search_multiplier": 50.0,
                    "current_product_pages_multiplier": 20.0,
                }
            ]
        }

    monkeypatch.setattr(
        "amazon_ads_mcp.warehouse.validation.get_placement_report",
        fake_placement_report,
    )
    connection.execute(
        sp_placement_fact.insert().values(
            profile_id="profile-1",
            window_start=date(2026, 1, 1),
            window_end=date(2026, 1, 2),
            campaign_id="10",
            placement_type="top_of_search",
            campaign_name="Campaign A",
            impressions=1000,
            clicks=50,
            spend=25,
            sales_14d=200,
            purchases_14d=4,
            current_top_of_search_multiplier=50,
            current_product_pages_multiplier=20,
            context_retrieved_at=datetime.now(UTC),
            last_report_run_id="run-1",
        )
    )

    result = await validate_placement_report(
        connection,
        profile_id="profile-1",
        start_date="2026-01-01",
        end_date="2026-01-02",
    )

    assert result["matched"] is True
