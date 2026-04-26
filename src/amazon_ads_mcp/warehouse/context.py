"""Helpers for running warehouse loads through the existing auth and routing abstractions."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from ..auth.manager import AuthManager, get_auth_manager
from ..tools.region import set_active_region


@contextmanager
def warehouse_profile_context(
    *,
    profile_id: str,
    region: str,
    auth_manager: AuthManager | None = None,
) -> Iterator[None]:
    """Temporarily scope auth manager state to a worker profile and region."""
    manager = auth_manager or get_auth_manager()
    previous_profile_id = manager.get_active_profile_id()
    manager.set_active_profile_id(profile_id)

    previous_region = manager.get_active_region()
    provider = manager.provider
    provider_region_attr = getattr(provider, "_region", None) if provider else None
    if provider and hasattr(provider, "region_controlled_by_identity") and not provider.region_controlled_by_identity():
        if hasattr(provider, "_region"):
            provider._region = region

    try:
        yield
    finally:
        if previous_profile_id:
            manager.set_active_profile_id(previous_profile_id)
        else:
            manager.clear_active_profile_id()
        if provider and hasattr(provider, "_region") and provider_region_attr is not None:
            provider._region = previous_region or provider_region_attr


async def ensure_worker_region(region: str) -> None:
    """Apply region selection through the same tool helper used by live runtime."""
    result = await set_active_region(region)
    if isinstance(result, dict) and result.get("success") is False:
        raise RuntimeError(result.get("message") or "Failed to set worker region.")
