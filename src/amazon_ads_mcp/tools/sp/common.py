"""Shared helpers for Sponsored Products tools."""

from __future__ import annotations

from typing import Any, Optional

from ...auth.manager import get_auth_manager
from ...config.settings import Settings
from ...utils.http import get_http_client


DEFAULT_LIST_LIMIT = 25
MAX_LIST_LIMIT = 100
SP_CAMPAIGN_MEDIA_TYPE = "application/vnd.spCampaign.v3+json"
SP_AD_GROUP_MEDIA_TYPE = "application/vnd.spAdGroup.v3+json"
SP_KEYWORD_MEDIA_TYPE = "application/vnd.spKeyword.v3+json"


class SPContextError(RuntimeError):
    """Raised when Sponsored Products tools are missing required context."""


def clamp_limit(value: Optional[int], default: int = DEFAULT_LIST_LIMIT) -> int:
    """Clamp caller-provided list bounds to a small agent-friendly range."""
    if value is None:
        return default

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if parsed <= 0:
        return default

    return min(parsed, MAX_LIST_LIMIT)


def clamp_offset(value: Optional[int]) -> int:
    """Normalize offsets to a non-negative integer."""
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0

    return max(parsed, 0)


def normalize_id_list(values: Optional[list[str]]) -> list[str]:
    """Return a stable string list without blanks."""
    if not values:
        return []

    normalized = []
    for value in values:
        if value is None:
            continue
        item = str(value).strip()
        if item:
            normalized.append(item)
    return normalized


def require_sp_context():
    """Return the active auth manager, profile, and region for SP reads."""
    auth_manager = get_auth_manager()
    profile_id = auth_manager.get_active_profile_id()
    region = auth_manager.get_active_region()

    if not profile_id:
        raise SPContextError(
            "Sponsored Products tools require an active profile. Use set_active_profile first."
        )

    if not region:
        raise SPContextError(
            "Sponsored Products tools require an active region. Use set_region first."
        )

    return auth_manager, str(profile_id), str(region)


async def get_sp_client(auth_manager=None):
    """Create an authenticated client for Sponsored Products requests."""
    auth_manager = auth_manager or get_auth_manager()
    credentials = await auth_manager.get_active_credentials()
    base_url = credentials.base_url or Settings().region_endpoint
    return await get_http_client(
        authenticated=True,
        auth_manager=auth_manager,
        base_url=base_url,
    )


def media_headers(media_type: str) -> dict[str, str]:
    """Return explicit vendor media headers for Sponsored Products requests."""
    return {"Content-Type": media_type, "Accept": media_type}


async def sp_post(
    client: Any,
    path: str,
    payload: dict[str, Any],
    media_type: str,
) -> Any:
    """Send a Sponsored Products POST request with explicit media headers."""
    return await client.post(path, json=payload, headers=media_headers(media_type))


def extract_items(payload: Any, primary_key: str) -> list[dict[str, Any]]:
    """Extract a list of records from common Amazon Ads response shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for key in (primary_key, "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return []


def parse_number(value: Any) -> float | None:
    """Convert scalar metric values to floats when possible."""
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_divide(numerator: Any, denominator: Any) -> float | None:
    """Return a stable ratio or ``None`` when the inputs are unusable."""
    left = parse_number(numerator)
    right = parse_number(denominator)
    if left is None or right in (None, 0.0):
        return None
    return left / right


def normalize_term(value: Any) -> str:
    """Normalize free-text terms for cross-reference lookups."""
    return " ".join(str(value or "").strip().lower().split())
