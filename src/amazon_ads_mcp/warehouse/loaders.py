"""Warehouse dimension and fact loaders built on existing live tool semantics."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Connection

from .live_views import (
    fetch_live_campaigns,
    fetch_live_keywords,
    fetch_live_portfolios,
    fetch_live_profiles,
    get_campaign_budget_history,
    get_impression_share_report,
    get_keyword_performance,
    get_placement_report,
    get_portfolio_budget_usage,
    get_search_term_report,
)
from .repository import advance_watermark, upsert_dimension_rows, upsert_fact_rows
from .utils import normalize_date, normalize_datetime, utcnow


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    return normalize_date(value)


async def load_ads_profiles(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
) -> int:
    """Refresh the visible ads_profile dimension rows."""
    now = utcnow()
    rows = []
    for profile in await fetch_live_profiles():
        current_profile_id = str(profile.get("profileId", "")).strip()
        if current_profile_id != profile_id:
            continue
        account_info = profile.get("accountInfo") or {}
        rows.append(
            {
                "profile_id": current_profile_id,
                "region": region,
                "country_code": profile.get("countryCode"),
                "account_type": account_info.get("type"),
                "account_name": account_info.get("name"),
                "currency_code": profile.get("currencyCode"),
                "timezone": profile.get("timezone"),
                "first_seen_at": now,
                "last_refreshed_at": now,
            }
        )
    count = upsert_dimension_rows(connection, "ads_profile", rows)
    advance_watermark(
        connection,
        surface_name="ads_profile",
        profile_id=profile_id,
        region=region,
        last_snapshot_at=now,
        last_status="completed",
    )
    return count


async def load_portfolios(connection: Connection, *, profile_id: str, region: str) -> int:
    """Refresh current portfolio settings."""
    now = utcnow()
    live_rows = await fetch_live_portfolios(limit=100)
    rows = [
        {
            "profile_id": profile_id,
            "portfolio_id": row["portfolio_id"],
            "name": row.get("name"),
            "state": row.get("state"),
            "budget_scope": row.get("budget_scope"),
            "daily_budget": row.get("daily_budget"),
            "monthly_budget": row.get("monthly_budget"),
            "currency_code": row.get("currency_code"),
            "budget_policy": row.get("budget_policy"),
            "in_budget": row.get("in_budget"),
            "serving_status": row.get("serving_status"),
            "campaign_unspent_budget_sharing_state": row.get(
                "campaign_unspent_budget_sharing_state"
            ),
            "status_reasons_json": row.get("status_reasons") or [],
            "budget_start_date": _parse_date(row.get("budget_start_date")),
            "budget_end_date": _parse_date(row.get("budget_end_date")),
            "first_seen_at": now,
            "last_refreshed_at": now,
        }
        for row in live_rows
    ]
    count = upsert_dimension_rows(connection, "portfolio", rows)
    advance_watermark(
        connection,
        surface_name="list_portfolios",
        profile_id=profile_id,
        region=region,
        last_snapshot_at=now,
        last_status="completed",
    )
    return count


async def load_campaigns_and_ad_groups(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
) -> tuple[int, int, list[str], list[str]]:
    """Refresh campaign and ad-group dimensions from the live list surface."""
    now = utcnow()
    campaigns = await fetch_live_campaigns()
    campaign_rows = []
    ad_group_rows = []
    campaign_ids: list[str] = []
    ad_group_ids: list[str] = []
    for campaign in campaigns:
        campaign_id = campaign.get("campaign_id")
        if not campaign_id:
            continue
        campaign_ids.append(campaign_id)
        campaign_rows.append(
            {
                "profile_id": profile_id,
                "campaign_id": campaign_id,
                "portfolio_id": campaign.get("portfolio_id"),
                "name": campaign.get("name"),
                "state": campaign.get("state"),
                "serving_status": campaign.get("serving_status"),
                "budget": campaign.get("budget"),
                "budget_type": campaign.get("budget_type"),
                "start_date": _parse_date(campaign.get("start_date")),
                "end_date": _parse_date(campaign.get("end_date")),
                "first_seen_at": now,
                "last_refreshed_at": now,
            }
        )
        for ad_group in campaign.get("ad_groups", []):
            ad_group_id = ad_group.get("ad_group_id")
            if not ad_group_id:
                continue
            ad_group_ids.append(ad_group_id)
            ad_group_rows.append(
                {
                    "profile_id": profile_id,
                    "ad_group_id": ad_group_id,
                    "campaign_id": campaign_id,
                    "name": ad_group.get("name"),
                    "state": ad_group.get("state"),
                    "default_bid": ad_group.get("default_bid"),
                    "first_seen_at": now,
                    "last_refreshed_at": now,
                }
            )
    campaign_count = upsert_dimension_rows(connection, "sp_campaign", campaign_rows)
    ad_group_count = upsert_dimension_rows(connection, "sp_ad_group", ad_group_rows)
    advance_watermark(
        connection,
        surface_name="list_campaigns",
        profile_id=profile_id,
        region=region,
        last_snapshot_at=now,
        last_status="completed",
    )
    return campaign_count, ad_group_count, campaign_ids, ad_group_ids


async def load_keywords(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    campaign_ids: list[str],
) -> tuple[int, list[str]]:
    """Refresh current keyword context for the active campaign set."""
    now = utcnow()
    rows = []
    keyword_ids: list[str] = []
    for campaign_id in campaign_ids:
        for keyword in await fetch_live_keywords(campaign_id=campaign_id):
            keyword_id = str(keyword.get("keywordId", "")).strip()
            if not keyword_id:
                continue
            keyword_ids.append(keyword_id)
            rows.append(
                {
                    "profile_id": profile_id,
                    "keyword_id": keyword_id,
                    "campaign_id": str(keyword.get("campaignId", "")).strip(),
                    "ad_group_id": str(keyword.get("adGroupId", "")).strip(),
                    "keyword_text": keyword.get("keywordText"),
                    "match_type": keyword.get("matchType"),
                    "current_bid": keyword.get("bid"),
                    "bid_refreshed_at": now,
                    "first_seen_at": now,
                    "last_refreshed_at": now,
                }
            )
    count = upsert_dimension_rows(connection, "sp_keyword", rows)
    advance_watermark(
        connection,
        surface_name="sp_keyword",
        profile_id=profile_id,
        region=region,
        last_snapshot_at=now,
        last_status="completed",
    )
    return count, keyword_ids


async def load_keyword_performance(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    report_run_id: str,
    amazon_report_id: str,
) -> int:
    """Ingest keyword performance facts keyed by profile/window/keyword."""
    payload = await get_keyword_performance(
        start_date=start_date,
        end_date=end_date,
        limit=100,
        resume_from_report_id=amazon_report_id,
    )
    retrieved_at = utcnow()
    rows = [
        {
            "profile_id": profile_id,
            "window_start": normalize_date(start_date),
            "window_end": normalize_date(end_date),
            "keyword_id": row.get("keyword_id"),
            "campaign_id": row.get("campaign_id"),
            "ad_group_id": row.get("ad_group_id"),
            "keyword_text": row.get("keyword_text"),
            "match_type": row.get("match_type"),
            "current_bid": row.get("bid"),
            "impressions": row.get("impressions"),
            "clicks": row.get("clicks"),
            "spend": row.get("spend"),
            "sales_14d": row.get("sales"),
            "orders_14d": row.get("orders"),
            "last_report_run_id": report_run_id,
            "retrieved_at": retrieved_at,
        }
        for row in payload["rows"]
        if row.get("keyword_id")
    ]
    count = upsert_fact_rows(connection, "sp_keyword_performance_fact", rows)
    advance_watermark(
        connection,
        surface_name="get_keyword_performance",
        profile_id=profile_id,
        region=region,
        last_successful_window_end=normalize_date(end_date),
        last_attempted_at=retrieved_at,
        last_status="completed",
    )
    return count


async def load_search_terms(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    report_run_id: str,
    amazon_report_id: str,
) -> int:
    """Ingest normalized search-term facts with JSON targeting context."""
    payload = await get_search_term_report(
        start_date=start_date,
        end_date=end_date,
        limit=100,
        resume_from_report_id=amazon_report_id,
    )
    retrieved_at = utcnow()
    rows = [
        {
            "profile_id": profile_id,
            "window_start": normalize_date(start_date),
            "window_end": normalize_date(end_date),
            "campaign_id": row.get("campaign_id"),
            "ad_group_id": row.get("ad_group_id"),
            "normalized_search_term": " ".join(
                str(row.get("search_term") or "").strip().lower().split()
            ),
            "keyword_id": row.get("keyword_id") or None,
            "search_term": row.get("search_term"),
            "match_type": row.get("match_type"),
            "impressions": row.get("impressions"),
            "clicks": row.get("clicks"),
            "spend": row.get("spend"),
            "sales_14d": row.get("sales"),
            "orders_14d": row.get("orders"),
            "manually_targeted": row.get("manually_targeted"),
            "negated": row.get("negated"),
            "targeting_context_json": {
                "manual_target_ids": row.get("manual_target_ids") or [],
                "negative_target_ids": row.get("negative_target_ids") or [],
                "negative_match_types": row.get("negative_match_types") or [],
            },
            "last_report_run_id": report_run_id,
            "retrieved_at": retrieved_at,
        }
        for row in payload["rows"]
        if row.get("campaign_id") and row.get("ad_group_id")
    ]
    count = upsert_fact_rows(connection, "sp_search_term_fact", rows)
    advance_watermark(
        connection,
        surface_name="get_search_term_report",
        profile_id=profile_id,
        region=region,
        last_successful_window_end=normalize_date(end_date),
        last_attempted_at=retrieved_at,
        last_status="completed",
    )
    return count


async def load_budget_history(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    report_run_id: str,
    amazon_report_id: str,
) -> int:
    """Ingest daily campaign budget history facts."""
    payload = await get_campaign_budget_history(
        start_date=start_date,
        end_date=end_date,
        limit=100,
        resume_from_report_id=amazon_report_id,
    )
    retrieved_at = utcnow()
    rows = [
        {
            "profile_id": profile_id,
            "campaign_id": row.get("campaign_id"),
            "budget_date": normalize_date(row.get("date")),
            "campaign_name": row.get("campaign_name"),
            "daily_budget": row.get("daily_budget"),
            "spend": row.get("spend"),
            "utilization_pct": row.get("utilization_pct"),
            "hours_ran": row.get("hours_ran"),
            "last_report_run_id": report_run_id,
            "retrieved_at": retrieved_at,
        }
        for row in payload["rows"]
        if row.get("campaign_id") and row.get("date")
    ]
    count = upsert_fact_rows(connection, "sp_campaign_budget_history_fact", rows)
    advance_watermark(
        connection,
        surface_name="get_campaign_budget_history",
        profile_id=profile_id,
        region=region,
        last_successful_window_end=normalize_date(end_date),
        last_attempted_at=retrieved_at,
        last_status="completed",
    )
    return count


async def load_placement_report(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    report_run_id: str,
    amazon_report_id: str,
) -> int:
    """Ingest placement facts with retrieval-time multiplier context."""
    payload = await get_placement_report(
        start_date=start_date,
        end_date=end_date,
        limit=100,
        resume_from_report_id=amazon_report_id,
    )
    retrieved_at = utcnow()
    rows = [
        {
            "profile_id": profile_id,
            "window_start": normalize_date(start_date),
            "window_end": normalize_date(end_date),
            "campaign_id": row.get("campaign_id"),
            "placement_type": row.get("placement_type"),
            "campaign_name": row.get("campaign_name"),
            "impressions": row.get("impressions"),
            "clicks": row.get("clicks"),
            "spend": row.get("spend"),
            "sales_14d": row.get("sales14d"),
            "purchases_14d": row.get("purchases14d"),
            "current_top_of_search_multiplier": row.get(
                "current_top_of_search_multiplier"
            ),
            "current_product_pages_multiplier": row.get(
                "current_product_pages_multiplier"
            ),
            "context_retrieved_at": retrieved_at,
            "last_report_run_id": report_run_id,
        }
        for row in payload["rows"]
        if row.get("campaign_id") and row.get("placement_type")
    ]
    count = upsert_fact_rows(connection, "sp_placement_fact", rows)
    advance_watermark(
        connection,
        surface_name="get_placement_report",
        profile_id=profile_id,
        region=region,
        last_successful_window_end=normalize_date(end_date),
        last_attempted_at=retrieved_at,
        last_status="completed",
    )
    return count


async def load_impression_share(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    report_run_id: str,
    amazon_report_id: str,
) -> int:
    """Ingest impression-share facts with explicit availability diagnostics."""
    campaign_ids = [
        row["campaign_id"]
        for row in await fetch_live_campaigns()
        if row.get("campaign_id")
    ]
    payload = await get_impression_share_report(
        start_date=start_date,
        end_date=end_date,
        campaign_ids=campaign_ids,
        limit=100,
        resume_from_report_id=amazon_report_id,
    )
    retrieved_at = utcnow()
    availability = payload.get("availability") or {}
    rows = [
        {
            "profile_id": profile_id,
            "window_start": normalize_date(start_date),
            "window_end": normalize_date(end_date),
            "campaign_id": row.get("campaign_id"),
            "campaign_name": row.get("campaign_name"),
            "top_of_search_impression_share": row.get(
                "top_of_search_impression_share"
            ),
            "availability_state": availability.get("state", "available"),
            "availability_reason": availability.get("reason"),
            "diagnostic_json": availability,
            "last_report_run_id": report_run_id,
            "retrieved_at": retrieved_at,
        }
        for row in payload.get("rows", [])
        if row.get("campaign_id")
    ]
    returned_campaign_ids = {row["campaign_id"] for row in rows}
    for campaign_id in availability.get("missing_campaign_ids") or []:
        if campaign_id in returned_campaign_ids:
            continue
        rows.append(
            {
                "profile_id": profile_id,
                "window_start": normalize_date(start_date),
                "window_end": normalize_date(end_date),
                "campaign_id": campaign_id,
                "campaign_name": None,
                "top_of_search_impression_share": None,
                "availability_state": availability.get("state", "unavailable"),
                "availability_reason": availability.get("reason"),
                "diagnostic_json": availability,
                "last_report_run_id": report_run_id,
                "retrieved_at": retrieved_at,
            }
        )
    count = upsert_fact_rows(connection, "sp_impression_share_fact", rows)
    advance_watermark(
        connection,
        surface_name="get_impression_share_report",
        profile_id=profile_id,
        region=region,
        last_successful_window_end=normalize_date(end_date),
        last_attempted_at=retrieved_at,
        last_status=availability.get("state") or "completed",
        notes=availability,
    )
    return count


async def load_portfolio_usage_snapshot(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    portfolio_ids: list[str],
) -> int:
    """Ingest point-in-time portfolio budget usage snapshots."""
    if not portfolio_ids:
        return 0
    payload = await get_portfolio_budget_usage(portfolio_ids)
    snapshot_timestamp = utcnow()
    diagnostic_index = {
        item.get("portfolio_id"): item for item in payload.get("diagnostics", [])
    }
    rows = []
    for row in payload.get("rows", []):
        portfolio_id = row.get("portfolio_id")
        diagnostic = diagnostic_index.get(portfolio_id) or {}
        availability = row.get("availability") or {}
        rows.append(
            {
                "profile_id": profile_id,
                "portfolio_id": portfolio_id,
                "snapshot_timestamp": snapshot_timestamp,
                "cap_amount": row.get("cap_amount"),
                "current_spend": row.get("current_spend"),
                "remaining_budget": row.get("remaining_budget"),
                "utilization_pct": row.get("utilization_pct"),
                "usage_updated_timestamp": normalize_datetime(
                    row.get("usage_updated_timestamp")
                ),
                "availability_state": availability.get("state"),
                "availability_reason": availability.get("reason"),
                "diagnostic_json": {
                    "row_availability": availability,
                    "diagnostic": diagnostic,
                },
            }
        )
    returned_portfolio_ids = {row.get("portfolio_id") for row in rows}
    for portfolio_id, diagnostic in diagnostic_index.items():
        if not portfolio_id or portfolio_id in returned_portfolio_ids:
            continue
        rows.append(
            {
                "profile_id": profile_id,
                "portfolio_id": portfolio_id,
                "snapshot_timestamp": snapshot_timestamp,
                "cap_amount": None,
                "current_spend": None,
                "remaining_budget": None,
                "utilization_pct": None,
                "usage_updated_timestamp": None,
                "availability_state": "unavailable",
                "availability_reason": diagnostic.get("details"),
                "diagnostic_json": {
                    "row_availability": {
                        "state": "unavailable",
                        "reason": diagnostic.get("details"),
                    },
                    "diagnostic": diagnostic,
                },
            }
        )
    count = upsert_fact_rows(connection, "portfolio_budget_usage_snapshot", rows)
    advance_watermark(
        connection,
        surface_name="get_portfolio_budget_usage",
        profile_id=profile_id,
        region=region,
        last_snapshot_at=snapshot_timestamp,
        last_attempted_at=snapshot_timestamp,
        last_status=(payload.get("availability") or {}).get("state") or "completed",
        notes=payload.get("availability") or {},
    )
    return count
