"""Sponsored Products impression-share reporting."""

from __future__ import annotations

from datetime import date
from typing import Any

from .common import clamp_limit, get_sp_client, normalize_id_list, parse_number, require_sp_context
from .report_helper import SPReportError, resume_sp_report, run_sp_report


DEFAULT_IMPRESSION_SHARE_TIMEOUT_SECONDS = 120.0
IMPRESSION_SHARE_REPORT_COLUMNS = [
    "campaignId",
    "campaignName",
    "adGroupId",
    "adGroupName",
    "keywordId",
    "keyword",
    "matchType",
    "impressionShare",
    "searchTermImpressionShare",
    "lostImpressionShareBudget",
    "searchTermImpressionShareLostToBudget",
    "lostImpressionShareRank",
    "searchTermImpressionShareLostToRank",
]
IMPRESSION_SHARE_FILTERS = [
    {"field": "keywordType", "values": ["BROAD", "PHRASE", "EXACT"]}
]
_CAMPAIGN_NAME_KEYS = ("campaignName", "campaign")
_AD_GROUP_NAME_KEYS = ("adGroupName", "adGroup")
_KEYWORD_ID_KEYS = ("keywordId", "targetId")
_KEYWORD_TEXT_KEYS = ("keywordText", "keyword", "targetingText", "targeting")
_MATCH_TYPE_KEYS = ("matchType", "keywordType", "targetingMatchType")
_IMPRESSION_SHARE_KEYS = (
    "impressionShare",
    "searchTermImpressionShare",
    "impression_share",
    "impressionSharePercent",
)
_LOST_IS_BUDGET_KEYS = (
    "lostImpressionShareBudget",
    "searchTermImpressionShareLostToBudget",
    "lostISBudget",
    "lost_is_budget",
)
_LOST_IS_RANK_KEYS = (
    "lostImpressionShareRank",
    "searchTermImpressionShareLostToRank",
    "lostISRank",
    "lost_is_rank",
)


def _validate_report_window(start_date: str, end_date: str) -> None:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError(
            "Impression-share reports require YYYY-MM-DD date inputs."
        ) from exc

    if start > end:
        raise ValueError(
            "Impression-share report start_date must be on or before end_date."
        )


def _first_present_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_share_metric(value: Any) -> float | None:
    parsed = parse_number(value)
    if parsed is None:
        return None
    if 0.0 <= parsed <= 1.0:
        return parsed * 100.0
    return parsed


def _matches_requested_scope(
    row: dict[str, Any],
    campaign_ids: list[str],
    ad_group_ids: list[str],
    keyword_ids: list[str],
) -> bool:
    if campaign_ids and str(row.get("campaignId", "")) not in campaign_ids:
        return False
    if ad_group_ids and str(row.get("adGroupId", "")) not in ad_group_ids:
        return False
    keyword_id = _first_present_value(row, _KEYWORD_ID_KEYS)
    if keyword_ids and str(keyword_id or "") not in keyword_ids:
        return False
    return True


def _normalize_impression_share_row(row: dict[str, Any]) -> dict[str, Any]:
    campaign_id = str(row.get("campaignId", ""))
    keyword_id = _first_present_value(row, _KEYWORD_ID_KEYS)

    return {
        "campaign_id": campaign_id,
        "campaign_name": _first_present_value(row, _CAMPAIGN_NAME_KEYS),
        "ad_group_id": str(row.get("adGroupId", "")) or None,
        "ad_group_name": _first_present_value(row, _AD_GROUP_NAME_KEYS),
        "keyword_id": str(keyword_id) if keyword_id not in (None, "") else None,
        "keyword_text": _first_present_value(row, _KEYWORD_TEXT_KEYS),
        "match_type": _first_present_value(row, _MATCH_TYPE_KEYS),
        "impression_share": _normalize_share_metric(
            _first_present_value(row, _IMPRESSION_SHARE_KEYS)
        ),
        "lost_is_budget": _normalize_share_metric(
            _first_present_value(row, _LOST_IS_BUDGET_KEYS)
        ),
        "lost_is_rank": _normalize_share_metric(
            _first_present_value(row, _LOST_IS_RANK_KEYS)
        ),
    }


def _build_coverage(
    rows: list[dict[str, Any]],
    campaign_ids: list[str],
    ad_group_ids: list[str],
    keyword_ids: list[str],
) -> dict[str, Any]:
    returned_campaign_ids = sorted(
        {row["campaign_id"] for row in rows if row.get("campaign_id")}
    )
    returned_ad_group_ids = sorted(
        {row["ad_group_id"] for row in rows if row.get("ad_group_id")}
    )
    returned_keyword_ids = sorted(
        {row["keyword_id"] for row in rows if row.get("keyword_id")}
    )

    missing_campaign_ids = sorted(set(campaign_ids) - set(returned_campaign_ids))
    missing_ad_group_ids = sorted(set(ad_group_ids) - set(returned_ad_group_ids))
    missing_keyword_ids = sorted(set(keyword_ids) - set(returned_keyword_ids))

    if not rows and (campaign_ids or ad_group_ids or keyword_ids):
        state = "unavailable"
        reason = (
            "Impression-share data could not be retrieved for the requested scope."
        )
    elif missing_campaign_ids or missing_ad_group_ids or missing_keyword_ids:
        state = "partial"
        reason = (
            "Impression-share data was only available for part of the requested scope."
        )
    else:
        state = "available"
        reason = None

    return {
        "state": state,
        "reason": reason,
        "missing_campaign_ids": missing_campaign_ids,
        "missing_ad_group_ids": missing_ad_group_ids,
        "missing_keyword_ids": missing_keyword_ids,
    }


def _classify_unavailable_result(error: SPReportError) -> dict[str, Any] | None:
    diagnostic = " ".join(
        part
        for part in (str(error), error.response_text)
        if isinstance(part, str) and part.strip()
    ).lower()
    if not diagnostic and error.status_code is None:
        return None

    if any(marker in diagnostic for marker in ("brand registry", "ineligible", "not eligible")):
        state = "ineligible"
        reason = (
            "Impression-share data is not available for the active advertiser or profile because the source appears ineligible."
        )
    elif any(
        marker in diagnostic
        for marker in (
            "unsupported",
            "not supported",
            "not enabled",
            "not entitled",
        )
    ):
        state = "unsupported"
        reason = (
            "Impression-share data is not supported for the active advertiser, profile, or requested scope."
        )
    elif error.status_code in {400, 403, 404, 405, 406, 422} or any(
        marker in diagnostic for marker in ("unavailable", "not available")
    ):
        state = "unavailable"
        reason = (
            "Impression-share data is currently unavailable for the active advertiser, profile, or requested scope."
        )
    else:
        return None

    return {
        "state": state,
        "reason": reason,
        "status_code": error.status_code,
        "diagnostic": diagnostic or None,
    }


def _build_unavailable_response(
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
    availability: dict[str, Any],
) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "region": region,
        "start_date": start_date,
        "end_date": end_date,
        "report_id": resume_from_report_id,
        "filters": {
            "campaign_ids": campaign_ids,
            "ad_group_ids": ad_group_ids,
            "keyword_ids": keyword_ids,
            "limit": limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
        "availability": {
            **availability,
            "missing_campaign_ids": campaign_ids,
            "missing_ad_group_ids": ad_group_ids,
            "missing_keyword_ids": keyword_ids,
        },
        "rows": [],
        "returned_count": 0,
    }


async def get_impression_share_report(
    start_date: str,
    end_date: str,
    campaign_ids: list[str] | None = None,
    ad_group_ids: list[str] | None = None,
    keyword_ids: list[str] | None = None,
    limit: int = 100,
    resume_from_report_id: str | None = None,
    timeout_seconds: float = DEFAULT_IMPRESSION_SHARE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Return normalized Sponsored Products impression-share rows."""
    _validate_report_window(start_date, end_date)

    auth_manager, profile_id, region = require_sp_context()
    client = await get_sp_client(auth_manager)

    normalized_campaign_ids = normalize_id_list(campaign_ids)
    normalized_ad_group_ids = normalize_id_list(ad_group_ids)
    normalized_keyword_ids = normalize_id_list(keyword_ids)

    try:
        if resume_from_report_id:
            report = await resume_sp_report(resume_from_report_id, client=client)
        else:
            report = await run_sp_report(
                report_type_id="spTargeting",
                start_date=start_date,
                end_date=end_date,
                group_by=["targeting"],
                columns=IMPRESSION_SHARE_REPORT_COLUMNS,
                filters=IMPRESSION_SHARE_FILTERS,
                timeout_seconds=timeout_seconds,
                client=client,
            )
    except SPReportError as exc:
        availability = _classify_unavailable_result(exc)
        if availability is None:
            raise
        return _build_unavailable_response(
            profile_id=profile_id,
            region=region,
            start_date=start_date,
            end_date=end_date,
            campaign_ids=normalized_campaign_ids,
            ad_group_ids=normalized_ad_group_ids,
            keyword_ids=normalized_keyword_ids,
            limit=clamp_limit(limit, default=100),
            resume_from_report_id=resume_from_report_id,
            timeout_seconds=timeout_seconds,
            availability=availability,
        )

    bounded_limit = clamp_limit(limit, default=100)
    filtered_rows = [
        row
        for row in report["rows"]
        if _matches_requested_scope(
            row,
            normalized_campaign_ids,
            normalized_ad_group_ids,
            normalized_keyword_ids,
        )
    ]
    rows = [
        _normalize_impression_share_row(row)
        for row in filtered_rows[:bounded_limit]
    ]
    coverage = _build_coverage(
        rows,
        normalized_campaign_ids,
        normalized_ad_group_ids,
        normalized_keyword_ids,
    )

    return {
        "profile_id": profile_id,
        "region": region,
        "start_date": start_date,
        "end_date": end_date,
        "report_id": report["report_id"],
        "filters": {
            "campaign_ids": normalized_campaign_ids,
            "ad_group_ids": normalized_ad_group_ids,
            "keyword_ids": normalized_keyword_ids,
            "limit": bounded_limit,
            "resume_from_report_id": resume_from_report_id,
            "timeout_seconds": timeout_seconds,
        },
        "availability": coverage,
        "rows": rows,
        "returned_count": len(rows),
    }
