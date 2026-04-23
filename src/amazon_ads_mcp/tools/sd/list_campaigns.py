"""Sponsored Display campaign discovery."""

from __future__ import annotations

from typing import Any

import httpx

from ...models.sd_models import (
    SDCampaign,
    SDCampaignListRequest,
    SDCampaignListResponse,
    SDTargetingGroupContext,
)
from .common import (
    SD_QUERY_CONTENT_TYPE,
    clamp_limit,
    clamp_offset,
    extract_campaign_budget,
    extract_campaign_budget_type,
    extract_items,
    get_sd_client,
    normalize_id_list,
    require_sd_context,
    sd_post,
)

_OBJECTIVE_KEYS = ("objective", "campaignObjective")
_BIDDING_MODEL_KEYS = ("biddingModel", "costType")
_TARGETING_GROUP_ID_KEYS = ("targetId", "adGroupId")
_TARGETING_GROUP_NAME_KEYS = ("name",)


def _first_present_value(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_targeting_group(item: dict[str, Any]) -> SDTargetingGroupContext:
    targeting_group_id = _first_present_value(item, _TARGETING_GROUP_ID_KEYS)
    targeting_group_name = _first_present_value(item, _TARGETING_GROUP_NAME_KEYS)
    return SDTargetingGroupContext(
        targeting_group_id=str(targeting_group_id) if targeting_group_id is not None else None,
        targeting_group_name=targeting_group_name,
        state=item.get("state"),
    )


def _normalize_campaign(
    campaign: dict[str, Any], targeting_groups: list[dict[str, Any]]
) -> SDCampaign:
    return SDCampaign(
        campaign_id=str(campaign.get("campaignId", "")),
        name=campaign.get("name"),
        state=campaign.get("state"),
        serving_status=campaign.get("servingStatus"),
        budget=extract_campaign_budget(campaign),
        budget_type=extract_campaign_budget_type(campaign),
        start_date=campaign.get("startDate"),
        end_date=campaign.get("endDate"),
        objective=_first_present_value(campaign, _OBJECTIVE_KEYS),
        bidding_model=_first_present_value(campaign, _BIDDING_MODEL_KEYS),
        targeting_groups=[
            _normalize_targeting_group(targeting_group)
            for targeting_group in targeting_groups
        ],
    )


async def _fetch_targeting_groups(client, campaign_ids: list[str]) -> list[dict[str, Any]]:
    if not campaign_ids:
        return []

    try:
        response = await sd_post(
            client,
            "/adsApi/v1/query/adGroups",
            {
                "adProductFilter": {"include": ["SPONSORED_DISPLAY"]},
                "campaignIdFilter": {"include": campaign_ids},
                "maxResults": clamp_limit(len(campaign_ids) * 20, default=100),
            },
            SD_QUERY_CONTENT_TYPE,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return []

    return extract_items(response.json(), "adGroups")


async def list_sd_campaigns(
    campaign_states: list[str] | None = None,
    campaign_ids: list[str] | None = None,
    objectives: list[str] | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Return Sponsored Display campaigns with available targeting-group context."""
    auth_manager, profile_id, region = require_sd_context()
    client = await get_sd_client(auth_manager)

    request = SDCampaignListRequest(
        campaign_states=[
            state.strip().upper() for state in campaign_states or [] if str(state).strip()
        ],
        campaign_ids=normalize_id_list(campaign_ids),
        objectives=[
            objective.strip().upper()
            for objective in objectives or []
            if str(objective).strip()
        ],
        limit=clamp_limit(limit),
        offset=clamp_offset(offset),
    )

    campaign_request: dict[str, Any] = {
        "adProductFilter": {"include": ["SPONSORED_DISPLAY"]},
        "maxResults": request.limit,
    }
    if request.campaign_states:
        campaign_request["stateFilter"] = {"include": request.campaign_states}
    if request.campaign_ids:
        campaign_request["campaignIdFilter"] = {"include": request.campaign_ids}

    campaign_response = await sd_post(
        client,
        "/adsApi/v1/query/campaigns",
        campaign_request,
        SD_QUERY_CONTENT_TYPE,
    )
    campaign_response.raise_for_status()
    campaign_items = extract_items(campaign_response.json(), "campaigns")

    if request.offset:
        campaign_items = campaign_items[request.offset : request.offset + request.limit]

    if request.objectives:
        campaign_items = [
            item
            for item in campaign_items
            if str(_first_present_value(item, _OBJECTIVE_KEYS) or "").strip().upper()
            in request.objectives
        ]

    returned_campaign_ids = [
        str(item.get("campaignId"))
        for item in campaign_items
        if item.get("campaignId") is not None
    ]
    targeting_group_items = await _fetch_targeting_groups(client, returned_campaign_ids)

    targeting_groups_by_campaign: dict[str, list[dict[str, Any]]] = {}
    for targeting_group in targeting_group_items:
        campaign_id = targeting_group.get("campaignId")
        if campaign_id is None:
            continue
        targeting_groups_by_campaign.setdefault(str(campaign_id), []).append(targeting_group)

    campaigns = [
        _normalize_campaign(
            campaign,
            targeting_groups_by_campaign.get(str(campaign.get("campaignId", "")), []),
        )
        for campaign in campaign_items[: request.limit]
    ]

    response = SDCampaignListResponse(
        profile_id=profile_id,
        region=region,
        filters=request,
        campaigns=campaigns,
        returned_count=len(campaigns),
    )
    return response.model_dump(mode="json")
