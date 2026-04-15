"""Sponsored Products campaign hierarchy browsing."""

from __future__ import annotations

from typing import Any

from .common import (
    SP_AD_GROUP_MEDIA_TYPE,
    SP_CAMPAIGN_MEDIA_TYPE,
    clamp_limit,
    clamp_offset,
    extract_items,
    get_sp_client,
    normalize_id_list,
    parse_number,
    require_sp_context,
    sp_post,
)


def _normalize_campaign(
    campaign: dict[str, Any], ad_groups: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "campaign_id": str(campaign.get("campaignId", "")),
        "name": campaign.get("name"),
        "state": campaign.get("state"),
        "serving_status": campaign.get("servingStatus"),
        "budget": parse_number(campaign.get("budget")),
        "budget_type": campaign.get("budgetType"),
        "start_date": campaign.get("startDate"),
        "end_date": campaign.get("endDate"),
        "ad_groups": [
            {
                "ad_group_id": str(ad_group.get("adGroupId", "")),
                "campaign_id": str(ad_group.get("campaignId", "")),
                "name": ad_group.get("name"),
                "state": ad_group.get("state"),
                "default_bid": parse_number(ad_group.get("defaultBid")),
            }
            for ad_group in ad_groups
        ],
    }


async def list_campaigns(
    campaign_states: list[str] | None = None,
    campaign_ids: list[str] | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Return Sponsored Products campaigns together with their ad groups."""
    auth_manager, profile_id, region = require_sp_context()
    client = await get_sp_client(auth_manager)

    normalized_campaign_ids = normalize_id_list(campaign_ids)
    normalized_states = [
        state.strip().upper() for state in campaign_states or [] if str(state).strip()
    ]
    bounded_limit = clamp_limit(limit)
    bounded_offset = clamp_offset(offset)

    campaign_request = {
        "count": bounded_limit,
        "startIndex": bounded_offset,
    }
    if normalized_states:
        campaign_request["stateFilter"] = normalized_states
    if normalized_campaign_ids:
        campaign_request["campaignIdFilter"] = normalized_campaign_ids

    campaign_response = await sp_post(
        client,
        "/sp/campaigns/list",
        campaign_request,
        SP_CAMPAIGN_MEDIA_TYPE,
    )
    campaign_response.raise_for_status()
    campaign_items = extract_items(campaign_response.json(), "campaigns")

    returned_campaign_ids = [
        str(item.get("campaignId"))
        for item in campaign_items
        if item.get("campaignId") is not None
    ]

    ad_group_items: list[dict[str, Any]] = []
    if returned_campaign_ids:
        ad_group_response = await sp_post(
            client,
            "/sp/adGroups/list",
            {
                "campaignIdFilter": returned_campaign_ids,
                "count": clamp_limit(len(returned_campaign_ids) * 20),
            },
            SP_AD_GROUP_MEDIA_TYPE,
        )
        ad_group_response.raise_for_status()
        ad_group_items = extract_items(ad_group_response.json(), "adGroups")

    ad_groups_by_campaign: dict[str, list[dict[str, Any]]] = {}
    for ad_group in ad_group_items:
        campaign_id = str(ad_group.get("campaignId", ""))
        ad_groups_by_campaign.setdefault(campaign_id, []).append(ad_group)

    campaigns = [
        _normalize_campaign(
            campaign, ad_groups_by_campaign.get(str(campaign.get("campaignId", "")), [])
        )
        for campaign in campaign_items
    ]

    return {
        "profile_id": profile_id,
        "region": region,
        "filters": {
            "campaign_states": normalized_states,
            "campaign_ids": normalized_campaign_ids,
            "limit": bounded_limit,
            "offset": bounded_offset,
        },
        "campaigns": campaigns,
        "returned_count": len(campaigns),
    }
