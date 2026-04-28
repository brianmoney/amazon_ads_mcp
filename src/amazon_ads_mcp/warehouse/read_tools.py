"""Warehouse-backed read helpers and MCP tool implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import json
from typing import Any, TypedDict

from sqlalchemy import Connection, select

from ..tools.portfolio.budget_usage import get_portfolio_budget_usage
from ..tools.portfolio.common import (
    normalize_required_portfolio_ids,
    parse_number as parse_portfolio_number,
    require_portfolio_context,
)
from ..tools.sp.campaign_budget_history import get_campaign_budget_history
from ..tools.sp.common import (
    MAX_LIST_LIMIT,
    clamp_limit,
    normalize_id_list,
    parse_number,
    require_sp_context,
    safe_divide,
)
from ..tools.sp.impression_share import get_impression_share_report
from ..tools.sp.keyword_performance import get_keyword_performance
from ..tools.sp.placement_report import get_placement_report
from ..tools.sp.search_term_report import get_search_term_report
from .db import warehouse_connection
from .schema import (
    freshness_watermark,
    ingestion_job,
    portfolio,
    portfolio_budget_usage_snapshot,
    report_run,
    sp_campaign_budget_history_fact,
    sp_impression_share_fact,
    sp_keyword_performance_fact,
    sp_placement_fact,
    sp_search_term_fact,
)
from .utils import normalize_date, utcnow


READ_PREFERENCES = {"prefer_warehouse", "warehouse_only", "live_only"}

WAREHOUSE_TOOL_TO_SURFACE = {
    "warehouse_get_keyword_performance": "get_keyword_performance",
    "warehouse_get_search_term_report": "get_search_term_report",
    "warehouse_get_campaign_budget_history": "get_campaign_budget_history",
    "warehouse_get_placement_report": "get_placement_report",
    "warehouse_get_impression_share_report": "get_impression_share_report",
    "warehouse_get_portfolio_budget_usage": "get_portfolio_budget_usage",
}
SURFACE_TO_WAREHOUSE_TOOL = {
    surface_name: warehouse_name
    for warehouse_name, surface_name in WAREHOUSE_TOOL_TO_SURFACE.items()
}

_PARTIAL_PORTFOLIO_REASON = (
    "Portfolio budget usage data was only partially available for the "
    "requested scope."
)
_UNAVAILABLE_PORTFOLIO_REASON = (
    "Portfolio budget usage data could not be retrieved for the requested "
    "scope."
)
_UNAVAILABLE_IMPRESSION_SHARE_REASON = (
    "Impression-share data could not be retrieved for the requested scope."
)


class WarehouseFallbackReason(TypedDict, total=False):
    """Structured reason describing why warehouse data was not served."""

    code: str
    message: str
    details: dict[str, Any]


class WarehouseFreshness(TypedDict, total=False):
    """Shared freshness details returned in warehouse provenance metadata."""

    surface_name: str
    warehouse_tool_name: str
    freshness_status: str
    eligible: bool
    max_staleness_minutes: int | None
    age_minutes: float | None
    last_successful_window_end: str | None
    last_snapshot_at: str | None
    last_attempted_at: str | None
    last_status: str | None
    notes: dict[str, Any]


class WarehouseProvenance(TypedDict, total=False):
    """Shared provenance envelope attached to warehouse-prefixed responses."""

    data_source: str
    read_preference: str
    freshness: WarehouseFreshness
    fallback_reason: WarehouseFallbackReason | None
    warehouse_context: dict[str, Any]


@dataclass
class WarehouseLookupResult:
    """Result of a warehouse eligibility and lookup attempt."""

    payload: dict[str, Any] | None
    freshness: WarehouseFreshness
    fallback_reason: WarehouseFallbackReason | None = None
    warehouse_context: dict[str, Any] | None = None


def _coerce_record(row: Any) -> dict[str, Any]:
    mapping = getattr(row, "_mapping", row)
    return dict(mapping)


def _serialize_scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_scalar(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _serialize_scalar(item) for key, item in value.items()
        }
    return value


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return []
        if isinstance(parsed, list):
            return parsed
    return []


def _normalize_surface_name(surface_name: str) -> str:
    normalized = str(surface_name or "").strip()
    if normalized in WAREHOUSE_TOOL_TO_SURFACE:
        return WAREHOUSE_TOOL_TO_SURFACE[normalized]
    if normalized in SURFACE_TO_WAREHOUSE_TOOL:
        return normalized
    supported = ", ".join(sorted(SURFACE_TO_WAREHOUSE_TOOL))
    raise ValueError(
        f"surface_name must be one of: {supported}"
    )


def _normalize_read_preference(read_preference: str) -> str:
    normalized = str(read_preference or "prefer_warehouse").strip().lower()
    if normalized not in READ_PREFERENCES:
        supported = ", ".join(sorted(READ_PREFERENCES))
        raise ValueError(
            f"read_preference must be one of: {supported}"
        )
    return normalized


def _normalize_staleness(value: int | None) -> int | None:
    if value is None:
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError("max_staleness_minutes must be >= 0")
    return parsed


def _build_fallback_reason(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> WarehouseFallbackReason:
    reason: WarehouseFallbackReason = {
        "code": code,
        "message": message,
    }
    if details:
        reason["details"] = {
            str(key): _serialize_scalar(value) for key, value in details.items()
        }
    return reason


def _lookup_watermark(
    connection: Connection,
    *,
    surface_name: str,
    profile_id: str,
    region: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        select(freshness_watermark).where(
            freshness_watermark.c.surface_name == surface_name,
            freshness_watermark.c.profile_id == profile_id,
            freshness_watermark.c.region == region,
        )
    ).one_or_none()
    if row is None:
        return None
    record = _coerce_record(row)
    record["notes_json"] = _json_object(record.get("notes_json"))
    return record


def _build_freshness(
    *,
    surface_name: str,
    max_staleness_minutes: int | None,
    watermark: dict[str, Any] | None,
) -> tuple[WarehouseFreshness, WarehouseFallbackReason | None]:
    warehouse_tool_name = SURFACE_TO_WAREHOUSE_TOOL[surface_name]
    freshness: WarehouseFreshness = {
        "surface_name": surface_name,
        "warehouse_tool_name": warehouse_tool_name,
        "freshness_status": "missing",
        "eligible": False,
        "max_staleness_minutes": max_staleness_minutes,
        "age_minutes": None,
        "last_successful_window_end": None,
        "last_snapshot_at": None,
        "last_attempted_at": None,
        "last_status": None,
        "notes": {},
    }
    if watermark is None:
        return (
            freshness,
            _build_fallback_reason(
                "missing_freshness",
                "Warehouse freshness metadata is missing for this surface.",
            ),
        )

    notes = watermark.get("notes_json") or {}
    observed_at = watermark.get("last_snapshot_at") or watermark.get(
        "last_attempted_at"
    )
    age_minutes = None
    if isinstance(observed_at, datetime):
        age_minutes = round(
            (utcnow() - observed_at).total_seconds() / 60.0,
            3,
        )

    freshness.update(
        {
            "freshness_status": "fresh",
            "eligible": True,
            "age_minutes": age_minutes,
            "last_successful_window_end": _serialize_scalar(
                watermark.get("last_successful_window_end")
            ),
            "last_snapshot_at": _serialize_scalar(
                watermark.get("last_snapshot_at")
            ),
            "last_attempted_at": _serialize_scalar(
                watermark.get("last_attempted_at")
            ),
            "last_status": _serialize_scalar(watermark.get("last_status")),
            "notes": _serialize_scalar(notes) or {},
        }
    )

    if max_staleness_minutes is None:
        return freshness, None
    if age_minutes is None:
        freshness["freshness_status"] = "stale"
        freshness["eligible"] = False
        return (
            freshness,
            _build_fallback_reason(
                "stale_data",
                "Warehouse freshness could not be verified against the requested "
                "staleness bound.",
                details={"max_staleness_minutes": max_staleness_minutes},
            ),
        )
    if age_minutes > max_staleness_minutes:
        freshness["freshness_status"] = "stale"
        freshness["eligible"] = False
        return (
            freshness,
            _build_fallback_reason(
                "stale_data",
                "Warehouse data exceeded the requested staleness bound.",
                details={
                    "age_minutes": age_minutes,
                    "max_staleness_minutes": max_staleness_minutes,
                },
            ),
        )
    return freshness, None


def _lookup_report_coverage(
    connection: Connection,
    *,
    surface_name: str,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
) -> tuple[dict[str, Any] | None, WarehouseFallbackReason | None]:
    window_start = normalize_date(start_date)
    window_end = normalize_date(end_date)
    row = connection.execute(
        select(report_run)
        .join(
            ingestion_job,
            ingestion_job.c.ingestion_job_id == report_run.c.ingestion_job_id,
        )
        .where(
            report_run.c.profile_id == profile_id,
            report_run.c.surface_name == surface_name,
            report_run.c.window_start == window_start,
            report_run.c.window_end == window_end,
            report_run.c.status == "completed",
            report_run.c.retrieved_at.is_not(None),
            ingestion_job.c.region == region,
        )
        .order_by(report_run.c.requested_at.desc())
    ).first()
    if row is None:
        return (
            None,
            _build_fallback_reason(
                "incomplete_coverage",
                "Warehouse data does not include a completed cached result for "
                "the requested date window.",
                details={
                    "start_date": start_date,
                    "end_date": end_date,
                },
            ),
        )

    coverage = _coerce_record(row)
    row_count = coverage.get("row_count")
    if row_count is None:
        return (
            None,
            _build_fallback_reason(
                "incomplete_coverage",
                "Warehouse report coverage could not be verified for this "
                "surface.",
            ),
        )
    if int(row_count) > MAX_LIST_LIMIT:
        return (
            None,
            _build_fallback_reason(
                "incomplete_coverage",
                "Warehouse report results exceeded the cached row limit and may "
                "be incomplete.",
                details={
                    "row_count": int(row_count),
                    "cached_row_limit": MAX_LIST_LIMIT,
                },
            ),
        )
    return coverage, None


def _build_provenance(
    *,
    data_source: str,
    read_preference: str,
    freshness: WarehouseFreshness,
    fallback_reason: WarehouseFallbackReason | None = None,
    warehouse_context: dict[str, Any] | None = None,
) -> WarehouseProvenance:
    provenance: WarehouseProvenance = {
        "data_source": data_source,
        "read_preference": read_preference,
        "freshness": freshness,
        "fallback_reason": fallback_reason,
    }
    if warehouse_context:
        provenance["warehouse_context"] = {
            str(key): _serialize_scalar(value)
            for key, value in warehouse_context.items()
        }
    return provenance


def _attach_provenance(
    payload: dict[str, Any],
    *,
    data_source: str,
    read_preference: str,
    freshness: WarehouseFreshness,
    fallback_reason: WarehouseFallbackReason | None = None,
    warehouse_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(payload)
    result["provenance"] = _build_provenance(
        data_source=data_source,
        read_preference=read_preference,
        freshness=freshness,
        fallback_reason=fallback_reason,
        warehouse_context=warehouse_context,
    )
    return result


def _build_empty_report_payload(
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    filters: dict[str, Any],
) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "region": region,
        "start_date": start_date,
        "end_date": end_date,
        "report_id": None,
        "filters": filters,
        "rows": [],
        "returned_count": 0,
    }


def _build_keyword_unavailable_payload(
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str],
    ad_group_ids: list[str],
    keyword_ids: list[str],
    limit: int,
    resume_from_report_id: str | None,
    timeout_seconds: float,
    reason: WarehouseFallbackReason | None = None,
) -> dict[str, Any]:
    return _build_empty_report_payload(
        profile_id=profile_id,
        region=region,
        start_date=start_date,
        end_date=end_date,
        filters={
            "campaign_ids": campaign_ids,
            "ad_group_ids": ad_group_ids,
            "keyword_ids": keyword_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
    )


def _build_search_term_unavailable_payload(
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str],
    limit: int,
    resume_from_report_id: str | None,
    timeout_seconds: float,
    reason: WarehouseFallbackReason | None = None,
) -> dict[str, Any]:
    return _build_empty_report_payload(
        profile_id=profile_id,
        region=region,
        start_date=start_date,
        end_date=end_date,
        filters={
            "campaign_ids": campaign_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
    )


def _build_budget_history_unavailable_payload(
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str],
    limit: int,
    resume_from_report_id: str | None,
    timeout_seconds: float,
    reason: WarehouseFallbackReason | None = None,
) -> dict[str, Any]:
    return _build_empty_report_payload(
        profile_id=profile_id,
        region=region,
        start_date=start_date,
        end_date=end_date,
        filters={
            "campaign_ids": campaign_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
    )


def _build_placement_unavailable_payload(
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str],
    limit: int,
    resume_from_report_id: str | None,
    timeout_seconds: float,
    reason: WarehouseFallbackReason | None = None,
) -> dict[str, Any]:
    return _build_empty_report_payload(
        profile_id=profile_id,
        region=region,
        start_date=start_date,
        end_date=end_date,
        filters={
            "campaign_ids": campaign_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
    )


def _build_impression_share_unavailable_payload(
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str],
    ad_group_ids: list[str],
    keyword_ids: list[str],
    limit: int,
    resume_from_report_id: str | None,
    timeout_seconds: float,
    reason: WarehouseFallbackReason,
) -> dict[str, Any]:
    availability_state = "unsupported"
    if reason["code"] != "unsupported_scope":
        availability_state = "unavailable"
    payload = _build_empty_report_payload(
        profile_id=profile_id,
        region=region,
        start_date=start_date,
        end_date=end_date,
        filters={
            "campaign_ids": campaign_ids,
            "ad_group_ids": ad_group_ids,
            "keyword_ids": keyword_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
    )
    payload["availability"] = {
        "state": availability_state,
        "reason": reason["message"],
        "missing_campaign_ids": campaign_ids,
        "missing_ad_group_ids": ad_group_ids,
        "missing_keyword_ids": keyword_ids,
    }
    return payload


def _build_portfolio_unavailable_payload(
    *,
    profile_id: str,
    region: str,
    portfolio_ids: list[str],
    reason: WarehouseFallbackReason,
) -> dict[str, Any]:
    diagnostics = [
        {
            "portfolio_id": portfolio_id,
            "state": "unavailable",
            "code": reason["code"].upper(),
            "details": reason["message"],
            "index": index,
        }
        for index, portfolio_id in enumerate(portfolio_ids)
    ]
    return {
        "profile_id": profile_id,
        "region": region,
        "filters": {"portfolio_ids": portfolio_ids},
        "availability": {
            "state": "unavailable",
            "reason": reason["message"],
            "missing_portfolio_ids": portfolio_ids,
        },
        "diagnostics": diagnostics,
        "rows": [],
        "returned_count": 0,
    }


async def _route_report_surface(
    *,
    surface_name: str,
    read_preference: str,
    max_staleness_minutes: int | None,
    live_kwargs: dict[str, Any],
    warehouse_loader,
    live_loader,
    unavailable_builder,
) -> dict[str, Any]:
    read_preference = _normalize_read_preference(read_preference)
    max_staleness_minutes = _normalize_staleness(max_staleness_minutes)
    _, profile_id, region = require_sp_context()

    if read_preference == "live_only":
        payload = await live_loader(**live_kwargs)
        return _attach_provenance(
            payload,
            data_source="live",
            read_preference=read_preference,
            freshness={
                "surface_name": surface_name,
                "warehouse_tool_name": SURFACE_TO_WAREHOUSE_TOOL[surface_name],
                "freshness_status": "skipped",
                "eligible": False,
                "max_staleness_minutes": max_staleness_minutes,
                "age_minutes": None,
                "last_successful_window_end": None,
                "last_snapshot_at": None,
                "last_attempted_at": None,
                "last_status": None,
                "notes": {},
            },
            fallback_reason=_build_fallback_reason(
                "live_only_requested",
                "Caller requested live execution for this warehouse-prefixed "
                "tool.",
            ),
        )

    try:
        with warehouse_connection() as connection:
            lookup = warehouse_loader(
                connection,
                profile_id=profile_id,
                region=region,
                max_staleness_minutes=max_staleness_minutes,
                **live_kwargs,
            )
    except Exception as exc:
        lookup = WarehouseLookupResult(
            payload=None,
            freshness={
                "surface_name": surface_name,
                "warehouse_tool_name": SURFACE_TO_WAREHOUSE_TOOL[surface_name],
                "freshness_status": "error",
                "eligible": False,
                "max_staleness_minutes": max_staleness_minutes,
                "age_minutes": None,
                "last_successful_window_end": None,
                "last_snapshot_at": None,
                "last_attempted_at": None,
                "last_status": None,
                "notes": {},
            },
            fallback_reason=_build_fallback_reason(
                "warehouse_lookup_failed",
                "Warehouse lookup failed for this surface.",
                details={"error": str(exc)},
            ),
        )

    if lookup.payload is not None:
        return _attach_provenance(
            lookup.payload,
            data_source="warehouse",
            read_preference=read_preference,
            freshness=lookup.freshness,
            warehouse_context=lookup.warehouse_context,
        )

    fallback_reason = lookup.fallback_reason or _build_fallback_reason(
        "missing_data",
        "Warehouse data was unavailable for this request.",
    )
    if read_preference == "warehouse_only":
        payload = unavailable_builder(
            profile_id=profile_id,
            region=region,
            reason=fallback_reason,
            **live_kwargs,
        )
        return _attach_provenance(
            payload,
            data_source="warehouse_unavailable",
            read_preference=read_preference,
            freshness=lookup.freshness,
            fallback_reason=fallback_reason,
            warehouse_context=lookup.warehouse_context,
        )

    payload = await live_loader(**live_kwargs)
    return _attach_provenance(
        payload,
        data_source="live",
        read_preference=read_preference,
        freshness=lookup.freshness,
        fallback_reason=fallback_reason,
        warehouse_context=lookup.warehouse_context,
    )


def _query_keyword_performance(
    connection: Connection,
    *,
    profile_id: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str],
    ad_group_ids: list[str],
    keyword_ids: list[str],
    limit: int,
) -> dict[str, Any]:
    rows = [
        _coerce_record(row)
        for row in connection.execute(
            select(sp_keyword_performance_fact)
            .where(
                sp_keyword_performance_fact.c.profile_id == profile_id,
                sp_keyword_performance_fact.c.window_start == normalize_date(start_date),
                sp_keyword_performance_fact.c.window_end == normalize_date(end_date),
            )
            .order_by(
                sp_keyword_performance_fact.c.campaign_id,
                sp_keyword_performance_fact.c.ad_group_id,
                sp_keyword_performance_fact.c.keyword_id,
            )
        )
    ]
    filtered_rows = [
        row
        for row in rows
        if (not campaign_ids or str(row.get("campaign_id")) in campaign_ids)
        and (not ad_group_ids or str(row.get("ad_group_id")) in ad_group_ids)
        and (not keyword_ids or str(row.get("keyword_id")) in keyword_ids)
    ]
    bounded_limit = clamp_limit(limit, default=100)
    return {
        "report_id": None,
        "filters": {
            "campaign_ids": campaign_ids,
            "ad_group_ids": ad_group_ids,
            "keyword_ids": keyword_ids,
            "limit": bounded_limit,
        },
        "rows": [
            {
                "campaign_id": str(row.get("campaign_id", "")),
                "campaign_name": None,
                "ad_group_id": str(row.get("ad_group_id", "")),
                "ad_group_name": None,
                "keyword_id": str(row.get("keyword_id", "")),
                "keyword_text": row.get("keyword_text"),
                "match_type": row.get("match_type"),
                "bid": parse_number(row.get("current_bid")),
                "impressions": parse_number(row.get("impressions")),
                "clicks": parse_number(row.get("clicks")),
                "spend": parse_number(row.get("spend")),
                "sales": parse_number(row.get("sales_14d")),
                "orders": parse_number(row.get("orders_14d")),
                "ctr": safe_divide(
                    row.get("clicks"),
                    row.get("impressions"),
                ),
                "cpc": safe_divide(
                    row.get("spend"),
                    row.get("clicks"),
                ),
                "acos": safe_divide(
                    row.get("spend"),
                    row.get("sales_14d"),
                ),
                "roas": safe_divide(
                    row.get("sales_14d"),
                    row.get("spend"),
                ),
            }
            for row in filtered_rows[:bounded_limit]
        ],
    }


def _lookup_keyword_performance(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None,
    ad_group_ids: list[str] | None,
    keyword_ids: list[str] | None,
    limit: int,
    resume_from_report_id: str | None,
    timeout_seconds: float,
    max_staleness_minutes: int | None,
) -> WarehouseLookupResult:
    normalized_campaign_ids = normalize_id_list(campaign_ids)
    normalized_ad_group_ids = normalize_id_list(ad_group_ids)
    normalized_keyword_ids = normalize_id_list(keyword_ids)
    watermark = _lookup_watermark(
        connection,
        surface_name="get_keyword_performance",
        profile_id=profile_id,
        region=region,
    )
    freshness, freshness_reason = _build_freshness(
        surface_name="get_keyword_performance",
        max_staleness_minutes=max_staleness_minutes,
        watermark=watermark,
    )
    if resume_from_report_id:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=_build_fallback_reason(
                "resume_request",
                "Warehouse reads cannot resume a specific live report_id.",
            ),
        )
    if freshness_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=freshness_reason,
        )
    coverage, coverage_reason = _lookup_report_coverage(
        connection,
        surface_name="get_keyword_performance",
        profile_id=profile_id,
        region=region,
        start_date=start_date,
        end_date=end_date,
    )
    if coverage_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=coverage_reason,
        )
    payload = _query_keyword_performance(
        connection,
        profile_id=profile_id,
        start_date=start_date,
        end_date=end_date,
        campaign_ids=normalized_campaign_ids,
        ad_group_ids=normalized_ad_group_ids,
        keyword_ids=normalized_keyword_ids,
        limit=limit,
    )
    payload.update(
        {
            "profile_id": profile_id,
            "region": region,
            "start_date": start_date,
            "end_date": end_date,
            "returned_count": len(payload["rows"]),
        }
    )
    return WarehouseLookupResult(
        payload=payload,
        freshness=freshness,
        warehouse_context={
            "report_run_id": coverage["report_run_id"],
            "row_count": coverage["row_count"],
            "window_start": coverage["window_start"],
            "window_end": coverage["window_end"],
            "timeout_seconds": timeout_seconds,
        },
    )


def _query_search_term_report(
    connection: Connection,
    *,
    profile_id: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str],
    limit: int,
) -> dict[str, Any]:
    rows = [
        _coerce_record(row)
        for row in connection.execute(
            select(sp_search_term_fact)
            .where(
                sp_search_term_fact.c.profile_id == profile_id,
                sp_search_term_fact.c.window_start == normalize_date(start_date),
                sp_search_term_fact.c.window_end == normalize_date(end_date),
            )
            .order_by(
                sp_search_term_fact.c.campaign_id,
                sp_search_term_fact.c.ad_group_id,
                sp_search_term_fact.c.normalized_search_term,
            )
        )
    ]
    filtered_rows = [
        row
        for row in rows
        if not campaign_ids or str(row.get("campaign_id")) in campaign_ids
    ]
    bounded_limit = clamp_limit(limit, default=100)
    normalized_rows = [
        {
            "campaign_id": str(row.get("campaign_id", "")),
            "campaign_name": None,
            "ad_group_id": str(row.get("ad_group_id", "")),
            "ad_group_name": None,
            "keyword_id": str(row.get("keyword_id") or ""),
            "search_term": row.get("search_term"),
            "match_type": row.get("match_type"),
            "impressions": parse_number(row.get("impressions")),
            "clicks": parse_number(row.get("clicks")),
            "spend": parse_number(row.get("spend")),
            "sales": parse_number(row.get("sales_14d")),
            "orders": parse_number(row.get("orders_14d")),
            "manually_targeted": bool(row.get("manually_targeted")),
            "manual_target_ids": (row.get("targeting_context_json") or {}).get(
                "manual_target_ids",
                [],
            ),
            "negated": bool(row.get("negated")),
            "negative_target_ids": (
                row.get("targeting_context_json") or {}
            ).get("negative_target_ids", []),
            "negative_match_types": (
                row.get("targeting_context_json") or {}
            ).get("negative_match_types", []),
        }
        for row in filtered_rows[:bounded_limit]
    ]
    target_campaign_ids = campaign_ids or sorted(
        {
            row["campaign_id"]
            for row in normalized_rows
            if row.get("campaign_id")
        }
    )
    return {
        "report_id": None,
        "filters": {
            "campaign_ids": target_campaign_ids,
            "limit": bounded_limit,
            "resume_from_report_id": None,
        },
        "rows": normalized_rows,
    }


def _lookup_search_term_report(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None,
    limit: int,
    resume_from_report_id: str | None,
    timeout_seconds: float,
    max_staleness_minutes: int | None,
) -> WarehouseLookupResult:
    normalized_campaign_ids = normalize_id_list(campaign_ids)
    watermark = _lookup_watermark(
        connection,
        surface_name="get_search_term_report",
        profile_id=profile_id,
        region=region,
    )
    freshness, freshness_reason = _build_freshness(
        surface_name="get_search_term_report",
        max_staleness_minutes=max_staleness_minutes,
        watermark=watermark,
    )
    if resume_from_report_id:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=_build_fallback_reason(
                "resume_request",
                "Warehouse reads cannot resume a specific live report_id.",
            ),
        )
    if freshness_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=freshness_reason,
        )
    coverage, coverage_reason = _lookup_report_coverage(
        connection,
        surface_name="get_search_term_report",
        profile_id=profile_id,
        region=region,
        start_date=start_date,
        end_date=end_date,
    )
    if coverage_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=coverage_reason,
        )
    payload = _query_search_term_report(
        connection,
        profile_id=profile_id,
        start_date=start_date,
        end_date=end_date,
        campaign_ids=normalized_campaign_ids,
        limit=limit,
    )
    payload.update(
        {
            "profile_id": profile_id,
            "region": region,
            "start_date": start_date,
            "end_date": end_date,
            "returned_count": len(payload["rows"]),
        }
    )
    payload["filters"]["resume_from_report_id"] = resume_from_report_id
    payload["filters"]["timeout_seconds"] = timeout_seconds
    return WarehouseLookupResult(
        payload=payload,
        freshness=freshness,
        warehouse_context={
            "report_run_id": coverage["report_run_id"],
            "row_count": coverage["row_count"],
            "window_start": coverage["window_start"],
            "window_end": coverage["window_end"],
        },
    )


def _query_budget_history(
    connection: Connection,
    *,
    profile_id: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str],
    limit: int,
) -> dict[str, Any]:
    rows = [
        _coerce_record(row)
        for row in connection.execute(
            select(sp_campaign_budget_history_fact)
            .where(
                sp_campaign_budget_history_fact.c.profile_id == profile_id,
                sp_campaign_budget_history_fact.c.budget_date
                >= normalize_date(start_date),
                sp_campaign_budget_history_fact.c.budget_date
                <= normalize_date(end_date),
            )
            .order_by(
                sp_campaign_budget_history_fact.c.budget_date,
                sp_campaign_budget_history_fact.c.campaign_id,
            )
        )
    ]
    filtered_rows = [
        row
        for row in rows
        if not campaign_ids or str(row.get("campaign_id")) in campaign_ids
    ]
    bounded_limit = clamp_limit(limit, default=100)
    return {
        "report_id": None,
        "filters": {
            "campaign_ids": campaign_ids,
            "limit": bounded_limit,
        },
        "rows": [
            {
                "date": _serialize_scalar(row.get("budget_date")),
                "campaign_id": str(row.get("campaign_id", "")),
                "campaign_name": row.get("campaign_name"),
                "daily_budget": parse_number(row.get("daily_budget")),
                "spend": parse_number(row.get("spend")),
                "utilization_pct": parse_number(row.get("utilization_pct")),
                "hours_ran": parse_number(row.get("hours_ran")),
            }
            for row in filtered_rows[:bounded_limit]
        ],
    }


def _lookup_budget_history(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None,
    limit: int,
    resume_from_report_id: str | None,
    timeout_seconds: float,
    max_staleness_minutes: int | None,
) -> WarehouseLookupResult:
    normalized_campaign_ids = normalize_id_list(campaign_ids)
    watermark = _lookup_watermark(
        connection,
        surface_name="get_campaign_budget_history",
        profile_id=profile_id,
        region=region,
    )
    freshness, freshness_reason = _build_freshness(
        surface_name="get_campaign_budget_history",
        max_staleness_minutes=max_staleness_minutes,
        watermark=watermark,
    )
    if resume_from_report_id:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=_build_fallback_reason(
                "resume_request",
                "Warehouse reads cannot resume a specific live report_id.",
            ),
        )
    if freshness_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=freshness_reason,
        )
    coverage, coverage_reason = _lookup_report_coverage(
        connection,
        surface_name="get_campaign_budget_history",
        profile_id=profile_id,
        region=region,
        start_date=start_date,
        end_date=end_date,
    )
    if coverage_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=coverage_reason,
        )
    payload = _query_budget_history(
        connection,
        profile_id=profile_id,
        start_date=start_date,
        end_date=end_date,
        campaign_ids=normalized_campaign_ids,
        limit=limit,
    )
    payload.update(
        {
            "profile_id": profile_id,
            "region": region,
            "start_date": start_date,
            "end_date": end_date,
            "returned_count": len(payload["rows"]),
        }
    )
    payload["filters"]["resume_from_report_id"] = resume_from_report_id
    payload["filters"]["timeout_seconds"] = timeout_seconds
    return WarehouseLookupResult(
        payload=payload,
        freshness=freshness,
        warehouse_context={
            "report_run_id": coverage["report_run_id"],
            "row_count": coverage["row_count"],
            "window_start": coverage["window_start"],
            "window_end": coverage["window_end"],
        },
    )


def _query_placement_report(
    connection: Connection,
    *,
    profile_id: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str],
    limit: int,
) -> dict[str, Any]:
    rows = [
        _coerce_record(row)
        for row in connection.execute(
            select(sp_placement_fact)
            .where(
                sp_placement_fact.c.profile_id == profile_id,
                sp_placement_fact.c.window_start == normalize_date(start_date),
                sp_placement_fact.c.window_end == normalize_date(end_date),
            )
            .order_by(
                sp_placement_fact.c.campaign_id,
                sp_placement_fact.c.placement_type,
            )
        )
    ]
    filtered_rows = [
        row
        for row in rows
        if not campaign_ids or str(row.get("campaign_id")) in campaign_ids
    ]
    bounded_limit = clamp_limit(limit, default=100)
    return {
        "report_id": None,
        "filters": {
            "campaign_ids": campaign_ids,
            "limit": bounded_limit,
        },
        "rows": [
            {
                "campaign_id": str(row.get("campaign_id", "")),
                "campaign_name": row.get("campaign_name"),
                "placement_type": row.get("placement_type"),
                "impressions": parse_number(row.get("impressions")),
                "clicks": parse_number(row.get("clicks")),
                "spend": parse_number(row.get("spend")),
                "sales14d": parse_number(row.get("sales_14d")),
                "purchases14d": parse_number(row.get("purchases_14d")),
                "ctr": safe_divide(
                    row.get("clicks"),
                    row.get("impressions"),
                ),
                "cpc": safe_divide(
                    row.get("spend"),
                    row.get("clicks"),
                ),
                "acos": safe_divide(
                    row.get("spend"),
                    row.get("sales_14d"),
                ),
                "roas": safe_divide(
                    row.get("sales_14d"),
                    row.get("spend"),
                ),
                "current_top_of_search_multiplier": parse_number(
                    row.get("current_top_of_search_multiplier")
                ),
                "current_product_pages_multiplier": parse_number(
                    row.get("current_product_pages_multiplier")
                ),
            }
            for row in filtered_rows[:bounded_limit]
        ],
    }


def _lookup_placement_report(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None,
    limit: int,
    resume_from_report_id: str | None,
    timeout_seconds: float,
    max_staleness_minutes: int | None,
) -> WarehouseLookupResult:
    normalized_campaign_ids = normalize_id_list(campaign_ids)
    watermark = _lookup_watermark(
        connection,
        surface_name="get_placement_report",
        profile_id=profile_id,
        region=region,
    )
    freshness, freshness_reason = _build_freshness(
        surface_name="get_placement_report",
        max_staleness_minutes=max_staleness_minutes,
        watermark=watermark,
    )
    if resume_from_report_id:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=_build_fallback_reason(
                "resume_request",
                "Warehouse reads cannot resume a specific live report_id.",
            ),
        )
    if freshness_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=freshness_reason,
        )
    coverage, coverage_reason = _lookup_report_coverage(
        connection,
        surface_name="get_placement_report",
        profile_id=profile_id,
        region=region,
        start_date=start_date,
        end_date=end_date,
    )
    if coverage_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=coverage_reason,
        )
    payload = _query_placement_report(
        connection,
        profile_id=profile_id,
        start_date=start_date,
        end_date=end_date,
        campaign_ids=normalized_campaign_ids,
        limit=limit,
    )
    payload.update(
        {
            "profile_id": profile_id,
            "region": region,
            "start_date": start_date,
            "end_date": end_date,
            "returned_count": len(payload["rows"]),
        }
    )
    payload["filters"]["resume_from_report_id"] = resume_from_report_id
    payload["filters"]["timeout_seconds"] = timeout_seconds
    return WarehouseLookupResult(
        payload=payload,
        freshness=freshness,
        warehouse_context={
            "report_run_id": coverage["report_run_id"],
            "row_count": coverage["row_count"],
            "window_start": coverage["window_start"],
            "window_end": coverage["window_end"],
        },
    )


def _query_impression_share(
    connection: Connection,
    *,
    profile_id: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str],
    limit: int,
) -> dict[str, Any]:
    rows = [
        _coerce_record(row)
        for row in connection.execute(
            select(sp_impression_share_fact)
            .where(
                sp_impression_share_fact.c.profile_id == profile_id,
                sp_impression_share_fact.c.window_start == normalize_date(start_date),
                sp_impression_share_fact.c.window_end == normalize_date(end_date),
            )
            .order_by(sp_impression_share_fact.c.campaign_id)
        )
    ]
    filtered_rows = [
        row
        for row in rows
        if not campaign_ids or str(row.get("campaign_id")) in campaign_ids
    ]
    bounded_limit = clamp_limit(limit, default=100)
    normalized_rows = [
        {
            "campaign_id": str(row.get("campaign_id", "")),
            "campaign_name": row.get("campaign_name"),
            "top_of_search_impression_share": parse_number(
                row.get("top_of_search_impression_share")
            ),
        }
        for row in filtered_rows
        if row.get("top_of_search_impression_share") is not None
    ][:bounded_limit]
    returned_campaign_ids = {
        row["campaign_id"] for row in normalized_rows if row.get("campaign_id")
    }
    missing_campaign_ids = sorted(
        set(campaign_ids) - returned_campaign_ids
    )
    if not normalized_rows and campaign_ids:
        availability = {
            "state": "unavailable",
            "reason": _UNAVAILABLE_IMPRESSION_SHARE_REASON,
            "missing_campaign_ids": campaign_ids,
            "missing_ad_group_ids": [],
            "missing_keyword_ids": [],
        }
    elif missing_campaign_ids:
        availability = {
            "state": "partial",
            "reason": (
                "Impression-share data was only available for part of the "
                "requested scope."
            ),
            "missing_campaign_ids": missing_campaign_ids,
            "missing_ad_group_ids": [],
            "missing_keyword_ids": [],
        }
    else:
        availability = {
            "state": "available",
            "reason": None,
            "missing_campaign_ids": [],
            "missing_ad_group_ids": [],
            "missing_keyword_ids": [],
        }
    return {
        "report_id": None,
        "filters": {
            "campaign_ids": campaign_ids,
            "ad_group_ids": [],
            "keyword_ids": [],
            "limit": bounded_limit,
        },
        "availability": availability,
        "rows": normalized_rows,
    }


def _lookup_impression_share(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None,
    ad_group_ids: list[str] | None,
    keyword_ids: list[str] | None,
    limit: int,
    resume_from_report_id: str | None,
    timeout_seconds: float,
    max_staleness_minutes: int | None,
) -> WarehouseLookupResult:
    normalized_campaign_ids = normalize_id_list(campaign_ids)
    normalized_ad_group_ids = normalize_id_list(ad_group_ids)
    normalized_keyword_ids = normalize_id_list(keyword_ids)
    watermark = _lookup_watermark(
        connection,
        surface_name="get_impression_share_report",
        profile_id=profile_id,
        region=region,
    )
    freshness, freshness_reason = _build_freshness(
        surface_name="get_impression_share_report",
        max_staleness_minutes=max_staleness_minutes,
        watermark=watermark,
    )
    if normalized_ad_group_ids or normalized_keyword_ids:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=_build_fallback_reason(
                "unsupported_scope",
                "Warehouse impression-share reads are campaign-level only; "
                "ad_group_ids and keyword_ids are not supported.",
            ),
        )
    if resume_from_report_id:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=_build_fallback_reason(
                "resume_request",
                "Warehouse reads cannot resume a specific live report_id.",
            ),
        )
    if freshness_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=freshness_reason,
        )
    coverage, coverage_reason = _lookup_report_coverage(
        connection,
        surface_name="get_impression_share_report",
        profile_id=profile_id,
        region=region,
        start_date=start_date,
        end_date=end_date,
    )
    if coverage_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=coverage_reason,
        )
    payload = _query_impression_share(
        connection,
        profile_id=profile_id,
        start_date=start_date,
        end_date=end_date,
        campaign_ids=normalized_campaign_ids,
        limit=limit,
    )
    payload.update(
        {
            "profile_id": profile_id,
            "region": region,
            "start_date": start_date,
            "end_date": end_date,
            "returned_count": len(payload["rows"]),
        }
    )
    payload["filters"]["resume_from_report_id"] = resume_from_report_id
    payload["filters"]["timeout_seconds"] = timeout_seconds
    return WarehouseLookupResult(
        payload=payload,
        freshness=freshness,
        warehouse_context={
            "report_run_id": coverage["report_run_id"],
            "row_count": coverage["row_count"],
            "window_start": coverage["window_start"],
            "window_end": coverage["window_end"],
        },
    )


def _load_portfolio_settings(
    connection: Connection,
    *,
    profile_id: str,
    portfolio_ids: list[str],
) -> dict[str, dict[str, Any]]:
    rows = [
        _coerce_record(row)
        for row in connection.execute(
            select(portfolio).where(
                portfolio.c.profile_id == profile_id,
                portfolio.c.portfolio_id.in_(portfolio_ids),
            )
        )
    ]
    return {
        str(row.get("portfolio_id")): {
            "portfolio_id": str(row.get("portfolio_id", "")),
            "name": row.get("name"),
            "state": row.get("state"),
            "in_budget": row.get("in_budget"),
            "serving_status": row.get("serving_status"),
            "status_reasons": _json_list(row.get("status_reasons_json")),
            "campaign_unspent_budget_sharing_state": row.get(
                "campaign_unspent_budget_sharing_state"
            ),
            "budget_policy": row.get("budget_policy"),
            "budget_scope": row.get("budget_scope"),
            "cap_amount": parse_portfolio_number(
                row.get("daily_budget") or row.get("monthly_budget")
            ),
            "daily_budget": parse_portfolio_number(row.get("daily_budget")),
            "monthly_budget": parse_portfolio_number(row.get("monthly_budget")),
            "currency_code": row.get("currency_code"),
            "budget_start_date": _serialize_scalar(row.get("budget_start_date")),
            "budget_end_date": _serialize_scalar(row.get("budget_end_date")),
        }
        for row in rows
        if row.get("portfolio_id")
    }


def _query_portfolio_budget_usage(
    connection: Connection,
    *,
    profile_id: str,
    portfolio_ids: list[str],
) -> tuple[dict[str, Any], WarehouseFallbackReason | None, dict[str, Any] | None]:
    ordered_rows = [
        _coerce_record(row)
        for row in connection.execute(
            select(portfolio_budget_usage_snapshot)
            .where(
                portfolio_budget_usage_snapshot.c.profile_id == profile_id,
                portfolio_budget_usage_snapshot.c.portfolio_id.in_(portfolio_ids),
            )
            .order_by(
                portfolio_budget_usage_snapshot.c.snapshot_timestamp.desc(),
                portfolio_budget_usage_snapshot.c.portfolio_id,
            )
        )
    ]
    if not ordered_rows:
        return (
            {},
            _build_fallback_reason(
                "missing_data",
                "Warehouse portfolio usage snapshots are not available for this "
                "profile.",
            ),
            None,
        )

    snapshot_by_id: dict[str, dict[str, Any]] = {}
    for row in ordered_rows:
        portfolio_id = str(row.get("portfolio_id") or "")
        if portfolio_id and portfolio_id not in snapshot_by_id:
            snapshot_by_id[portfolio_id] = row
    snapshot_rows = list(snapshot_by_id.values())
    if len(snapshot_rows) != len(portfolio_ids):
        returned_ids = {
            str(row.get("portfolio_id")) for row in snapshot_rows
        }
        missing_ids = [
            portfolio_id
            for portfolio_id in portfolio_ids
            if portfolio_id not in returned_ids
        ]
        return (
            {},
            _build_fallback_reason(
                "incomplete_coverage",
                "Warehouse portfolio usage snapshots do not cover every requested "
                "portfolio_id.",
                details={"missing_portfolio_ids": missing_ids},
            ),
            None,
        )

    settings_by_id = _load_portfolio_settings(
        connection,
        profile_id=profile_id,
        portfolio_ids=portfolio_ids,
    )
    rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for index, portfolio_id in enumerate(portfolio_ids):
        snapshot = snapshot_by_id[portfolio_id]
        diagnostic_json = _json_object(snapshot.get("diagnostic_json"))
        availability = diagnostic_json.get("row_availability") or {
            "state": snapshot.get("availability_state"),
            "reason": snapshot.get("availability_reason"),
            "missing_fields": [],
        }
        diagnostic = diagnostic_json.get("diagnostic") or {}
        if snapshot.get("availability_state") == "unavailable":
            diagnostics.append(
                {
                    "portfolio_id": portfolio_id,
                    "state": "unavailable",
                    "code": str(diagnostic.get("code", "UNKNOWN")),
                    "details": diagnostic.get("details")
                    or snapshot.get("availability_reason"),
                    "index": diagnostic.get("index", index),
                }
            )
            continue

        settings = settings_by_id.get(portfolio_id) or {
            "portfolio_id": portfolio_id,
            "name": None,
            "state": None,
            "in_budget": None,
            "serving_status": None,
            "status_reasons": [],
            "campaign_unspent_budget_sharing_state": None,
            "budget_policy": None,
            "budget_scope": None,
            "cap_amount": None,
            "daily_budget": None,
            "monthly_budget": None,
            "currency_code": None,
            "budget_start_date": None,
            "budget_end_date": None,
        }
        cap_amount = parse_portfolio_number(snapshot.get("cap_amount"))
        current_spend = parse_portfolio_number(snapshot.get("current_spend"))
        remaining_budget = parse_portfolio_number(
            snapshot.get("remaining_budget")
        )
        rows.append(
            {
                "portfolio_id": portfolio_id,
                "name": settings.get("name"),
                "state": settings.get("state"),
                "in_budget": settings.get("in_budget"),
                "serving_status": settings.get("serving_status"),
                "status_reasons": settings.get("status_reasons", []),
                "campaign_unspent_budget_sharing_state": settings.get(
                    "campaign_unspent_budget_sharing_state"
                ),
                "budget_policy": settings.get("budget_policy"),
                "budget_scope": settings.get("budget_scope"),
                "cap_amount": cap_amount,
                "daily_budget": settings.get("daily_budget"),
                "monthly_budget": settings.get("monthly_budget"),
                "currency_code": settings.get("currency_code"),
                "budget_start_date": settings.get("budget_start_date"),
                "budget_end_date": settings.get("budget_end_date"),
                "current_spend": current_spend,
                "remaining_budget": remaining_budget,
                "utilization_pct": parse_portfolio_number(
                    snapshot.get("utilization_pct")
                ),
                "usage_updated_timestamp": _serialize_scalar(
                    snapshot.get("usage_updated_timestamp")
                ),
                "availability": availability,
            }
        )

    if not rows:
        availability = {
            "state": "unavailable",
            "reason": _UNAVAILABLE_PORTFOLIO_REASON,
            "missing_portfolio_ids": portfolio_ids,
        }
    elif diagnostics or any(
        row["availability"].get("state") != "available" for row in rows
    ):
        availability = {
            "state": "partial",
            "reason": _PARTIAL_PORTFOLIO_REASON,
            "missing_portfolio_ids": [
                item["portfolio_id"]
                for item in diagnostics
                if item.get("portfolio_id")
            ],
        }
    else:
        availability = {
            "state": "available",
            "reason": None,
            "missing_portfolio_ids": [],
        }
    return (
        {
            "filters": {"portfolio_ids": portfolio_ids},
            "availability": availability,
            "diagnostics": diagnostics,
            "rows": rows,
            "returned_count": len(rows),
        },
        None,
        {
            "snapshot_timestamps": sorted(
                {
                    _serialize_scalar(row.get("snapshot_timestamp"))
                    for row in snapshot_rows
                    if row.get("snapshot_timestamp") is not None
                }
            )
        },
    )


def _lookup_portfolio_budget_usage(
    connection: Connection,
    *,
    profile_id: str,
    region: str,
    portfolio_ids: list[str],
    max_staleness_minutes: int | None,
) -> WarehouseLookupResult:
    watermark = _lookup_watermark(
        connection,
        surface_name="get_portfolio_budget_usage",
        profile_id=profile_id,
        region=region,
    )
    freshness, freshness_reason = _build_freshness(
        surface_name="get_portfolio_budget_usage",
        max_staleness_minutes=max_staleness_minutes,
        watermark=watermark,
    )
    if freshness_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=freshness_reason,
        )
    payload, coverage_reason, warehouse_context = _query_portfolio_budget_usage(
        connection,
        profile_id=profile_id,
        portfolio_ids=portfolio_ids,
    )
    if coverage_reason is not None:
        return WarehouseLookupResult(
            payload=None,
            freshness=freshness,
            fallback_reason=coverage_reason,
        )
    payload.update({"profile_id": profile_id, "region": region})
    return WarehouseLookupResult(
        payload=payload,
        freshness=freshness,
        warehouse_context=warehouse_context,
    )


async def warehouse_get_surface_status(
    surface_name: str | None = None,
    read_preference: str = "prefer_warehouse",
    max_staleness_minutes: int | None = None,
) -> dict[str, Any]:
    """Return freshness metadata for supported warehouse-backed surfaces."""
    read_preference = _normalize_read_preference(read_preference)
    max_staleness_minutes = _normalize_staleness(max_staleness_minutes)
    _, profile_id, region = require_sp_context()

    if read_preference == "live_only":
        payload = {
            "profile_id": profile_id,
            "region": region,
            "surface_statuses": [],
            "returned_count": 0,
        }
        return _attach_provenance(
            payload,
            data_source="live",
            read_preference=read_preference,
            freshness={
                "surface_name": "warehouse_get_surface_status",
                "warehouse_tool_name": "warehouse_get_surface_status",
                "freshness_status": "skipped",
                "eligible": False,
                "max_staleness_minutes": max_staleness_minutes,
                "age_minutes": None,
                "last_successful_window_end": None,
                "last_snapshot_at": None,
                "last_attempted_at": None,
                "last_status": None,
                "notes": {},
            },
            fallback_reason=_build_fallback_reason(
                "live_only_requested",
                "Caller requested live execution for this warehouse-prefixed "
                "tool.",
            ),
        )

    if surface_name is None:
        surface_names = sorted(SURFACE_TO_WAREHOUSE_TOOL)
    else:
        surface_names = [_normalize_surface_name(surface_name)]

    try:
        with warehouse_connection() as connection:
            statuses = []
            for current_surface in surface_names:
                watermark = _lookup_watermark(
                    connection,
                    surface_name=current_surface,
                    profile_id=profile_id,
                    region=region,
                )
                freshness, _ = _build_freshness(
                    surface_name=current_surface,
                    max_staleness_minutes=max_staleness_minutes,
                    watermark=watermark,
                )
                statuses.append(
                    {
                        "surface_name": current_surface,
                        "warehouse_tool_name": SURFACE_TO_WAREHOUSE_TOOL[
                            current_surface
                        ],
                        "status": "missing"
                        if watermark is None
                        else "available",
                        "last_successful_window_end": freshness[
                            "last_successful_window_end"
                        ],
                        "last_snapshot_at": freshness["last_snapshot_at"],
                        "last_attempted_at": freshness["last_attempted_at"],
                        "last_status": freshness["last_status"],
                        "notes": freshness["notes"],
                    }
                )
    except Exception as exc:
        return {
            "profile_id": profile_id,
            "region": region,
            "surface_statuses": [
                {
                    "surface_name": current_surface,
                    "warehouse_tool_name": SURFACE_TO_WAREHOUSE_TOOL[
                        current_surface
                    ],
                    "status": "unavailable",
                    "last_successful_window_end": None,
                    "last_snapshot_at": None,
                    "last_attempted_at": None,
                    "last_status": None,
                    "notes": {},
                }
                for current_surface in surface_names
            ],
            "returned_count": len(surface_names),
            "provenance": _build_provenance(
                data_source="warehouse_unavailable",
                read_preference=read_preference,
                freshness={
                    "surface_name": "warehouse_get_surface_status",
                    "warehouse_tool_name": "warehouse_get_surface_status",
                    "freshness_status": "error",
                    "eligible": False,
                    "max_staleness_minutes": max_staleness_minutes,
                    "age_minutes": None,
                    "last_successful_window_end": None,
                    "last_snapshot_at": None,
                    "last_attempted_at": None,
                    "last_status": None,
                    "notes": {},
                },
                fallback_reason=_build_fallback_reason(
                    "warehouse_lookup_failed",
                    "Warehouse status lookup failed.",
                    details={"error": str(exc)},
                ),
            ),
        }

    payload = {
        "profile_id": profile_id,
        "region": region,
        "surface_statuses": statuses,
        "returned_count": len(statuses),
    }
    return _attach_provenance(
        payload,
        data_source="warehouse",
        read_preference=read_preference,
        freshness={
            "surface_name": "warehouse_get_surface_status",
            "warehouse_tool_name": "warehouse_get_surface_status",
            "freshness_status": "fresh",
            "eligible": True,
            "max_staleness_minutes": max_staleness_minutes,
            "age_minutes": None,
            "last_successful_window_end": None,
            "last_snapshot_at": None,
            "last_attempted_at": None,
            "last_status": None,
            "notes": {},
        },
    )


async def warehouse_get_keyword_performance(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    ad_group_ids: list[str] | None = None,
    keyword_ids: list[str] | None = None,
    limit: int = 100,
    resume_from_report_id: str | None = None,
    timeout_seconds: float = 360.0,
    read_preference: str = "prefer_warehouse",
    max_staleness_minutes: int | None = None,
) -> dict[str, Any]:
    """Return warehouse-backed keyword performance with live fallback."""
    normalize_date(start_date)
    normalize_date(end_date)
    return await _route_report_surface(
        surface_name="get_keyword_performance",
        read_preference=read_preference,
        max_staleness_minutes=max_staleness_minutes,
        live_kwargs={
            "start_date": start_date,
            "end_date": end_date,
            "campaign_ids": campaign_ids,
            "ad_group_ids": ad_group_ids,
            "keyword_ids": keyword_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
        warehouse_loader=_lookup_keyword_performance,
        live_loader=get_keyword_performance,
        unavailable_builder=_build_keyword_unavailable_payload,
    )


async def warehouse_get_search_term_report(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    limit: int = 100,
    resume_from_report_id: str | None = None,
    timeout_seconds: float = 120.0,
    read_preference: str = "prefer_warehouse",
    max_staleness_minutes: int | None = None,
) -> dict[str, Any]:
    """Return warehouse-backed search terms with live fallback."""
    normalize_date(start_date)
    normalize_date(end_date)
    return await _route_report_surface(
        surface_name="get_search_term_report",
        read_preference=read_preference,
        max_staleness_minutes=max_staleness_minutes,
        live_kwargs={
            "start_date": start_date,
            "end_date": end_date,
            "campaign_ids": campaign_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
        warehouse_loader=_lookup_search_term_report,
        live_loader=get_search_term_report,
        unavailable_builder=_build_search_term_unavailable_payload,
    )


async def warehouse_get_campaign_budget_history(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    limit: int = 100,
    resume_from_report_id: str | None = None,
    timeout_seconds: float = 120.0,
    read_preference: str = "prefer_warehouse",
    max_staleness_minutes: int | None = None,
) -> dict[str, Any]:
    """Return warehouse-backed budget history with live fallback."""
    normalize_date(start_date)
    normalize_date(end_date)
    return await _route_report_surface(
        surface_name="get_campaign_budget_history",
        read_preference=read_preference,
        max_staleness_minutes=max_staleness_minutes,
        live_kwargs={
            "start_date": start_date,
            "end_date": end_date,
            "campaign_ids": campaign_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
        warehouse_loader=_lookup_budget_history,
        live_loader=get_campaign_budget_history,
        unavailable_builder=_build_budget_history_unavailable_payload,
    )


async def warehouse_get_placement_report(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    limit: int = 100,
    resume_from_report_id: str | None = None,
    timeout_seconds: float = 120.0,
    read_preference: str = "prefer_warehouse",
    max_staleness_minutes: int | None = None,
) -> dict[str, Any]:
    """Return warehouse-backed placement data with live fallback."""
    normalize_date(start_date)
    normalize_date(end_date)
    return await _route_report_surface(
        surface_name="get_placement_report",
        read_preference=read_preference,
        max_staleness_minutes=max_staleness_minutes,
        live_kwargs={
            "start_date": start_date,
            "end_date": end_date,
            "campaign_ids": campaign_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
        warehouse_loader=_lookup_placement_report,
        live_loader=get_placement_report,
        unavailable_builder=_build_placement_unavailable_payload,
    )


async def warehouse_get_impression_share_report(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    ad_group_ids: list[str] | None = None,
    keyword_ids: list[str] | None = None,
    limit: int = 100,
    resume_from_report_id: str | None = None,
    timeout_seconds: float = 120.0,
    read_preference: str = "prefer_warehouse",
    max_staleness_minutes: int | None = None,
) -> dict[str, Any]:
    """Return warehouse-backed impression-share data with live fallback."""
    normalize_date(start_date)
    normalize_date(end_date)
    return await _route_report_surface(
        surface_name="get_impression_share_report",
        read_preference=read_preference,
        max_staleness_minutes=max_staleness_minutes,
        live_kwargs={
            "start_date": start_date,
            "end_date": end_date,
            "campaign_ids": campaign_ids,
            "ad_group_ids": ad_group_ids,
            "keyword_ids": keyword_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
        warehouse_loader=_lookup_impression_share,
        live_loader=get_impression_share_report,
        unavailable_builder=_build_impression_share_unavailable_payload,
    )


async def warehouse_get_portfolio_budget_usage(
    portfolio_ids: list[str],
    read_preference: str = "prefer_warehouse",
    max_staleness_minutes: int | None = None,
) -> dict[str, Any]:
    """Return warehouse-backed portfolio usage with live fallback."""
    read_preference = _normalize_read_preference(read_preference)
    max_staleness_minutes = _normalize_staleness(max_staleness_minutes)
    normalized_portfolio_ids = normalize_required_portfolio_ids(portfolio_ids)
    _, profile_id, region = require_portfolio_context()

    if read_preference == "live_only":
        payload = await get_portfolio_budget_usage(normalized_portfolio_ids)
        return _attach_provenance(
            payload,
            data_source="live",
            read_preference=read_preference,
            freshness={
                "surface_name": "get_portfolio_budget_usage",
                "warehouse_tool_name": "warehouse_get_portfolio_budget_usage",
                "freshness_status": "skipped",
                "eligible": False,
                "max_staleness_minutes": max_staleness_minutes,
                "age_minutes": None,
                "last_successful_window_end": None,
                "last_snapshot_at": None,
                "last_attempted_at": None,
                "last_status": None,
                "notes": {},
            },
            fallback_reason=_build_fallback_reason(
                "live_only_requested",
                "Caller requested live execution for this warehouse-prefixed "
                "tool.",
            ),
        )

    try:
        with warehouse_connection() as connection:
            lookup = _lookup_portfolio_budget_usage(
                connection,
                profile_id=profile_id,
                region=region,
                portfolio_ids=normalized_portfolio_ids,
                max_staleness_minutes=max_staleness_minutes,
            )
    except Exception as exc:
        lookup = WarehouseLookupResult(
            payload=None,
            freshness={
                "surface_name": "get_portfolio_budget_usage",
                "warehouse_tool_name": "warehouse_get_portfolio_budget_usage",
                "freshness_status": "error",
                "eligible": False,
                "max_staleness_minutes": max_staleness_minutes,
                "age_minutes": None,
                "last_successful_window_end": None,
                "last_snapshot_at": None,
                "last_attempted_at": None,
                "last_status": None,
                "notes": {},
            },
            fallback_reason=_build_fallback_reason(
                "warehouse_lookup_failed",
                "Warehouse lookup failed for this surface.",
                details={"error": str(exc)},
            ),
        )

    if lookup.payload is not None:
        return _attach_provenance(
            lookup.payload,
            data_source="warehouse",
            read_preference=read_preference,
            freshness=lookup.freshness,
            warehouse_context=lookup.warehouse_context,
        )

    fallback_reason = lookup.fallback_reason or _build_fallback_reason(
        "missing_data",
        "Warehouse data was unavailable for this request.",
    )
    if read_preference == "warehouse_only":
        payload = _build_portfolio_unavailable_payload(
            profile_id=profile_id,
            region=region,
            portfolio_ids=normalized_portfolio_ids,
            reason=fallback_reason,
        )
        return _attach_provenance(
            payload,
            data_source="warehouse_unavailable",
            read_preference=read_preference,
            freshness=lookup.freshness,
            fallback_reason=fallback_reason,
            warehouse_context=lookup.warehouse_context,
        )

    payload = await get_portfolio_budget_usage(normalized_portfolio_ids)
    return _attach_provenance(
        payload,
        data_source="live",
        read_preference=read_preference,
        freshness=lookup.freshness,
        fallback_reason=fallback_reason,
        warehouse_context=lookup.warehouse_context,
    )


__all__ = [
    "WAREHOUSE_TOOL_TO_SURFACE",
    "warehouse_get_campaign_budget_history",
    "warehouse_get_impression_share_report",
    "warehouse_get_keyword_performance",
    "warehouse_get_placement_report",
    "warehouse_get_portfolio_budget_usage",
    "warehouse_get_search_term_report",
    "warehouse_get_surface_status",
]
