"""Shared helpers for Sponsored Display tools."""

from __future__ import annotations

from typing import Any

from ...auth.manager import get_auth_manager
from ...config.settings import Settings
from ...utils.http import get_http_client
from ..sp.common import (
    clamp_limit,
    clamp_offset,
    extract_campaign_budget,
    extract_campaign_budget_type,
    extract_items,
    normalize_id_list,
    parse_number,
    safe_divide,
)

SD_CAMPAIGN_MEDIA_TYPE = "application/vnd.sdcampaign.v3+json"
SD_TARGETING_GROUP_MEDIA_TYPE = "application/vnd.sdtargetinggroup.v3+json"


class SDContextError(RuntimeError):
    """Raised when Sponsored Display tools are missing required context."""


def require_sd_context() -> tuple[Any, str, str]:
    """Return the active auth manager, profile, and region for SD reads."""
    auth_manager = get_auth_manager()
    profile_id = auth_manager.get_active_profile_id()
    region = auth_manager.get_active_region()

    if not profile_id:
        raise SDContextError(
            "Sponsored Display tools require an active profile. Use set_active_profile first."
        )

    if not region:
        raise SDContextError(
            "Sponsored Display tools require an active region. Use set_region first."
        )

    return auth_manager, str(profile_id), str(region)


async def get_sd_client(auth_manager=None):
    """Create an authenticated client for Sponsored Display requests."""
    auth_manager = auth_manager or get_auth_manager()
    credentials = await auth_manager.get_active_credentials()
    base_url = credentials.base_url or Settings().region_endpoint
    return await get_http_client(
        authenticated=True,
        auth_manager=auth_manager,
        base_url=base_url,
    )


def media_headers(media_type: str) -> dict[str, str]:
    """Return explicit vendor media headers for Sponsored Display requests."""
    return {"Content-Type": media_type, "Accept": media_type}


async def sd_post(
    client: Any,
    path: str,
    payload: dict[str, Any],
    media_type: str,
) -> Any:
    """Send a Sponsored Display POST request with explicit media headers."""
    return await client.post(path, json=payload, headers=media_headers(media_type))


__all__ = [
    "SDContextError",
    "SD_CAMPAIGN_MEDIA_TYPE",
    "SD_TARGETING_GROUP_MEDIA_TYPE",
    "clamp_limit",
    "clamp_offset",
    "extract_campaign_budget",
    "extract_campaign_budget_type",
    "extract_items",
    "get_sd_client",
    "normalize_id_list",
    "parse_number",
    "require_sd_context",
    "safe_divide",
    "sd_post",
]
