"""Register built-in tools for the MCP server.

Handle registration of identity, profile, region, sampling, and
authentication tools depending on the active provider.

Examples
--------
.. code-block:: python

   import asyncio
   from fastmcp import FastMCP
   from amazon_ads_mcp.server.builtin_tools import register_all_builtin_tools

   async def main():
       server = FastMCP("amazon-ads")
       await register_all_builtin_tools(server)

   asyncio.run(main())
"""

import logging
from typing import Optional

from fastmcp import Context, FastMCP

from ..auth.manager import get_auth_manager
from ..config.settings import settings
from ..models.builtin_responses import (
    ClearProfileResponse,
    GetProfileResponse,
    GetRegionResponse,
    ListRegionsResponse,
    ProfileSelectorResponse,
    ProfilePageResponse,
    ProfileCacheRefreshResponse,
    ProfileSearchResponse,
    ProfileSummaryResponse,
    RoutingStateResponse,
    SamplingTestResponse,
    SetProfileResponse,
    SetRegionResponse,
)
from ..tools import identity, profile, profile_listing, region
from ..tools.oauth import OAuthTools

# Removed http_client imports - override functions were removed

logger = logging.getLogger(__name__)


async def register_identity_tools(server: FastMCP):
    """Register identity management tools.

    :param server: FastMCP server instance.
    """

    @server.tool(
        name="set_active_identity",
        description="Set the active identity for Amazon Ads API calls",
    )
    async def set_active_identity_tool(
        ctx: Context,
        identity_id: str,
        persist: bool = False,
    ):
        """Set the active identity for API calls."""
        from ..models import SetActiveIdentityRequest

        req = SetActiveIdentityRequest(
            identity_id=identity_id,
            persist=persist,
        )
        return await identity.set_active_identity(req)

    @server.tool(
        name="get_active_identity",
        description="Get the currently active identity",
    )
    async def get_active_identity_tool(ctx: Context):
        """Get the currently active identity."""
        return await identity.get_active_identity()

    @server.tool(name="list_identities", description="List all available identities")
    async def list_identities_tool(ctx: Context) -> dict:
        """List all available identities."""
        return await identity.list_identities()


async def register_profile_tools(server: FastMCP):
    """Register profile management tools.

    :param server: FastMCP server instance.
    """

    @server.tool(
        name="set_active_profile",
        description="Set the active profile ID for API calls",
    )
    async def set_active_profile_tool(
        ctx: Context, profile_id: str
    ) -> SetProfileResponse:
        """Set the active profile ID."""
        result = await profile.set_active_profile(profile_id)
        return SetProfileResponse(**result)

    @server.tool(
        name="get_active_profile",
        description="Get the currently active profile ID",
    )
    async def get_active_profile_tool(ctx: Context) -> GetProfileResponse:
        """Get the currently active profile ID."""
        result = await profile.get_active_profile()
        return GetProfileResponse(**result)

    @server.tool(name="clear_active_profile", description="Clear the active profile ID")
    async def clear_active_profile_tool(ctx: Context) -> ClearProfileResponse:
        """Clear the active profile ID."""
        result = await profile.clear_active_profile()
        return ClearProfileResponse(**result)

    @server.tool(
        name="select_profile",
        description="Interactively select a profile from available options",
    )
    async def select_profile_tool(ctx: Context) -> ProfileSelectorResponse:
        """Interactively select an Amazon Ads profile.

        This tool uses MCP elicitation to present available profiles to the user
        and let them select one interactively. This is more user-friendly than
        requiring users to call list_profiles and set_active_profile separately.

        The tool will:
        1. Fetch available profiles from the Amazon Ads API
        2. Present them to the user via elicitation
        3. Set the selected profile as active
        4. Return the selection result
        """
        from dataclasses import dataclass

        from ..tools import profile_listing

        # Define the selection structure for elicitation
        @dataclass
        class ProfileSelection:
            profile_id: str

        # Fetch available profiles
        try:
            profiles_data, stale = await profile_listing.get_profiles_cached()
        except Exception as e:
            logger.error(f"Failed to fetch profiles: {e}")
            return ProfileSelectorResponse(
                success=False,
                action="cancel",
                message=f"Failed to fetch profiles: {e}",
            )

        if not profiles_data:
            return ProfileSelectorResponse(
                success=False,
                action="cancel",
                message="No profiles available. Please ensure you have access to advertising accounts.",
            )

        if len(profiles_data) > profile_listing.PROFILE_SELECTION_THRESHOLD:
            message = (
                "Too many profiles to display here. Use summarize_profiles, "
                "search_profiles, or page_profiles to locate the right profile."
            )
            if stale:
                message = "Using cached profile list; data may be stale. " + message
            return ProfileSelectorResponse(
                success=True,
                action="cancel",
                message=message,
            )

        # Build a formatted message with profile options
        profile_list = []
        for p in profiles_data:
            profile_id = str(p.get("profileId", ""))
            country = p.get("countryCode", "")
            account_info = p.get("accountInfo", {})
            account_name = account_info.get("name", "Unknown")
            account_type = account_info.get("type", "Unknown")
            profile_list.append(
                f"  - {profile_id}: {account_name} ({country}, {account_type})"
            )

        profiles_message = (
            f"Available profiles ({len(profiles_data)} found):\n"
            + "\n".join(profile_list)
            + "\n\nEnter the profile ID you want to use:"
        )

        # Use elicitation to let user select
        try:
            result = await ctx.elicit(
                message=profiles_message,
                response_type=ProfileSelection,
            )

            if result.action == "accept":
                selected_id = result.data.profile_id

                # Validate the selection
                valid_ids = [str(p.get("profileId", "")) for p in profiles_data]
                if selected_id not in valid_ids:
                    return ProfileSelectorResponse(
                        success=False,
                        action="accept",
                        message=f"Invalid profile ID: {selected_id}. Please select from the available profiles.",
                    )

                # Set the selected profile as active
                await profile.set_active_profile(selected_id)

                # Find the profile name for the response
                selected_profile = next(
                    (
                        p
                        for p in profiles_data
                        if str(p.get("profileId")) == selected_id
                    ),
                    None,
                )
                profile_name = (
                    selected_profile.get("accountInfo", {}).get("name", "Unknown")
                    if selected_profile
                    else "Unknown"
                )

                return ProfileSelectorResponse(
                    success=True,
                    action="accept",
                    profile_id=selected_id,
                    profile_name=profile_name,
                    message=f"Profile '{profile_name}' ({selected_id}) is now active.",
                )

            elif result.action == "decline":
                return ProfileSelectorResponse(
                    success=True,
                    action="decline",
                    message="Profile selection declined. No changes made.",
                )

            else:  # cancel
                return ProfileSelectorResponse(
                    success=True,
                    action="cancel",
                    message="Profile selection cancelled.",
                )

        except Exception as e:
            logger.error(f"Elicitation failed: {e}")
            return ProfileSelectorResponse(
                success=False,
                action="cancel",
                message=f"Profile selection failed: {e}",
            )


async def register_profile_listing_tools(server: FastMCP):
    """Register profile listing tools with bounded responses."""

    @server.tool(
        name="summarize_profiles",
        description="Summarize available profiles by country and account type",
    )
    async def summarize_profiles_tool(ctx: Context) -> ProfileSummaryResponse:
        """Summarize available profiles."""
        result = await profile_listing.summarize_profiles()
        return ProfileSummaryResponse(**result)

    @server.tool(
        name="search_profiles",
        description="Search profiles by name, country, or account type",
    )
    async def search_profiles_tool(
        ctx: Context,
        query: Optional[str] = None,
        country_code: Optional[str] = None,
        account_type: Optional[str] = None,
        limit: int = profile_listing.DEFAULT_SEARCH_LIMIT,
    ) -> ProfileSearchResponse:
        """Search profiles with bounded output."""
        result = await profile_listing.search_profiles(
            query=query,
            country_code=country_code,
            account_type=account_type,
            limit=limit,
        )
        return ProfileSearchResponse(**result)

    @server.tool(
        name="page_profiles",
        description="Page through profiles with offset and limit",
    )
    async def page_profiles_tool(
        ctx: Context,
        country_code: Optional[str] = None,
        account_type: Optional[str] = None,
        offset: int = 0,
        limit: int = profile_listing.DEFAULT_PAGE_LIMIT,
    ) -> ProfilePageResponse:
        """Return a page of profiles with bounded output."""
        result = await profile_listing.page_profiles(
            country_code=country_code,
            account_type=account_type,
            offset=offset,
            limit=limit,
        )
        return ProfilePageResponse(**result)

    @server.tool(
        name="refresh_profiles_cache",
        description="Force refresh of cached profiles for the current identity and region",
    )
    async def refresh_profiles_cache_tool(ctx: Context) -> ProfileCacheRefreshResponse:
        """Force refresh the cached profile list."""
        result = await profile_listing.refresh_profiles_cache()
        return ProfileCacheRefreshResponse(**result)


async def register_region_tools(server: FastMCP):
    """Register region management tools.

    :param server: FastMCP server instance.
    """

    @server.tool(
        name="set_region",
        description="Set the region for Amazon Ads API calls",
    )
    async def set_region_tool(ctx: Context, region_code: str) -> SetRegionResponse:
        """Set the region for API calls."""
        result = await region.set_region(region_code)
        return SetRegionResponse(**result)

    @server.tool(name="get_region", description="Get the current region setting")
    async def get_region_tool(ctx: Context) -> GetRegionResponse:
        """Get the current region."""
        result = await region.get_region()
        return GetRegionResponse(**result)

    @server.tool(name="list_regions", description="List all available regions")
    async def list_regions_tool(ctx: Context) -> ListRegionsResponse:
        """List available regions."""
        result = await region.list_regions()
        return ListRegionsResponse(**result)

    @server.tool(
        name="get_routing_state",
        description="Get the current routing state including region, host, and headers",
    )
    async def get_routing_state_tool(ctx: Context) -> RoutingStateResponse:
        """Get the complete routing state for debugging."""
        from ..utils.http_client import get_routing_state
        from ..utils.region_config import RegionConfig

        result = get_routing_state()

        # Provide defaults when no routing state has been established yet
        # (e.g., on a fresh server before any requests)
        current_region = settings.amazon_ads_region or "na"
        default_host = RegionConfig.get_api_host(current_region)

        # Apply sandbox host replacement (same pattern used in http_client.py)
        if settings.amazon_ads_sandbox_mode:
            default_host = default_host.replace(
                "advertising-api", "advertising-api-test"
            )

        return RoutingStateResponse(
            region=result.get("region", current_region),
            host=result.get("host", default_host),
            headers=result.get("headers", {}),
            sandbox=settings.amazon_ads_sandbox_mode,
        )


# Removed region_identity_tools - list_identities_by_region was just a convenience wrapper


# Routing override tools removed - use the main region/marketplace tools instead


async def register_sampling_tools(server: FastMCP):
    """Register sampling tools if sampling is enabled.

    :param server: FastMCP server instance
    :type server: FastMCP
    """
    if not settings.enable_sampling:
        return

    @server.tool(
        name="test_sampling",
        description="Test LLM sampling functionality via MCP client",
    )
    async def test_sampling_tool(
        ctx: Context,
        message: str = "Hello, please summarize this test message",
    ) -> SamplingTestResponse:
        """Test the native MCP sampling functionality.

        Uses FastMCP 2.14.1+ native ctx.sample() directly. This requires
        the MCP client to support sampling (createMessage capability).

        The sampling flow:
        1. Tool sends sampling request to client via ctx.sample()
        2. Client's LLM generates a response
        3. Response is returned to the tool

        Note: If the client doesn't support sampling, an error will be returned.
        Server-side fallback is available when SAMPLING_ENABLED=true and
        OPENAI_API_KEY is configured.
        """
        try:
            # Use native ctx.sample() - FastMCP 2.14.1+
            result = await ctx.sample(
                messages=message,
                system_prompt="You are a helpful assistant. Provide a brief summary.",
                temperature=0.7,
                max_tokens=100,
            )

            # Extract text from result
            response_text = result.text if hasattr(result, "text") else str(result)

            return SamplingTestResponse(
                success=True,
                message="Sampling executed successfully via native ctx.sample()",
                response=response_text,
                sampling_enabled=settings.enable_sampling,
            )
        except Exception as e:
            error_msg = str(e).lower()

            # Check if it's a "client doesn't support sampling" error
            if (
                "does not support sampling" in error_msg
                or "sampling not supported" in error_msg
            ):
                # Try server-side fallback if enabled
                if settings.enable_sampling:
                    try:
                        from ..utils.sampling_helpers import sample_with_fallback

                        result = await sample_with_fallback(
                            ctx=ctx,
                            messages=message,
                            system_prompt="You are a helpful assistant. Provide a brief summary.",
                            temperature=0.7,
                            max_tokens=100,
                        )
                        response_text = (
                            result.text if hasattr(result, "text") else str(result)
                        )

                        return SamplingTestResponse(
                            success=True,
                            message="Sampling executed via server-side fallback",
                            response=response_text,
                            sampling_enabled=True,
                            used_fallback="Server-side OpenAI fallback was used",
                        )
                    except Exception as fallback_error:
                        logger.error(f"Server-side fallback failed: {fallback_error}")
                        return SamplingTestResponse(
                            success=False,
                            error=f"Both client and server sampling failed: {fallback_error}",
                            sampling_enabled=True,
                            note="Check OPENAI_API_KEY environment variable",
                        )

                return SamplingTestResponse(
                    success=False,
                    error="Client does not support sampling",
                    sampling_enabled=False,
                    note="Enable server-side fallback with SAMPLING_ENABLED=true and OPENAI_API_KEY",
                )

            logger.error(f"Sampling test failed: {e}")
            return SamplingTestResponse(
                success=False,
                error=str(e),
                sampling_enabled=settings.enable_sampling,
            )


async def register_oauth_tools_builtin(server: FastMCP):
    """Register OAuth authentication tools.

    :param server: FastMCP server instance.
    """
    oauth = OAuthTools(settings)

    @server.tool(
        name="start_oauth_flow",
        description="Start the OAuth authorization flow for Amazon Ads API",
    )
    async def start_oauth_flow(ctx: Context):
        """Start the OAuth authorization flow."""
        return await oauth.start_oauth_flow(ctx)

    @server.tool(
        name="check_oauth_status",
        description="Check the current OAuth authentication status",
    )
    async def check_oauth_status(ctx: Context):
        """Check OAuth authentication status."""
        return await oauth.check_oauth_status(ctx)

    @server.tool(
        name="refresh_oauth_token",
        description="Manually refresh the OAuth access token",
    )
    async def refresh_oauth_token(ctx: Context):
        """Refresh OAuth access token."""
        return await oauth.refresh_access_token(ctx)

    @server.tool(
        name="clear_oauth_tokens",
        description="Clear all stored OAuth tokens and state",
    )
    async def clear_oauth_tokens(ctx: Context):
        """Clear OAuth tokens."""
        return await oauth.clear_oauth_tokens(ctx)

    logger.info("Registered OAuth authentication tools")


# Removed cache tools - not core operations


# Removed diagnostic tools - not core operations


async def register_all_builtin_tools(server: FastMCP):
    """Register all built-in tools with the server.

    :param server: FastMCP server instance.
    """
    # Register common tools that work for all auth types
    await register_profile_tools(server)
    await register_profile_listing_tools(server)
    await register_region_tools(server)
    # Routing tools removed - override functionality was redundant
    await register_sampling_tools(server)
    # Cache & diagnostic tools removed - not core operations

    # Register auth-specific tools based on provider type
    auth_mgr = get_auth_manager()
    if auth_mgr and auth_mgr.provider:
        # Check provider_type property (not auth_method attribute)
        if hasattr(auth_mgr.provider, "provider_type"):
            if auth_mgr.provider.provider_type == "direct":
                # Direct OAuth authentication tools
                await register_oauth_tools_builtin(server)
                logger.info("Registered OAuth authentication tools")
            elif auth_mgr.provider.provider_type == "openbridge":
                # OpenBridge identity management tools
                await register_identity_tools(server)
                logger.info("Registered OpenBridge identity tools")

    logger.info("Registered all built-in tools")
