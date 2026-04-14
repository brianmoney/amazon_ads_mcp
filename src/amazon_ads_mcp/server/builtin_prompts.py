"""Built-in prompts for the stripped utility-only server."""

from typing import TYPE_CHECKING

from ..auth.manager import get_auth_manager

if TYPE_CHECKING:
    from fastmcp import FastMCP


async def register_all_builtin_prompts(server: "FastMCP") -> None:
    """Register the retained built-in prompts."""

    auth_mgr = get_auth_manager()
    provider_type = getattr(getattr(auth_mgr, "provider", None), "provider_type", None)

    if provider_type == "direct":

        @server.prompt(
            name="auth_profile_setup",
            description="Complete authentication and profile setup for Amazon Ads API",
            tags={"auth", "profile", "setup"},
            meta={"version": "0.2", "owner": "ads-platform"},
            task=False,
        )
        def auth_profile_setup_prompt(region: str = "na") -> str:
            return (
                "Goal: Set up Amazon Ads API authentication and select an active profile.\n"
                "Steps for the model:\n"
                "1) Start OAuth flow if needed:\n"
                "   - Tool: start_oauth_flow\n"
                "   - Monitor with: check_oauth_status\n"
                "2) Set the region:\n"
                f"   - Tool: set_region (use '{region}')\n"
                "3) Discover available profiles safely:\n"
                "   - Tool: summarize_profiles\n"
                "   - Optional: search_profiles or page_profiles to locate a specific profile\n"
                "4) Set the active profile:\n"
                "   - Tool: set_active_profile\n"
                "5) Verify setup:\n"
                "   - Tool: get_routing_state\n"
                "   - Tool: get_active_profile\n"
                "   - Tool: check_oauth_status\n"
                "Return: Summary of authentication status, active region, and selected profile."
            )

    @server.prompt(
        name="troubleshoot_auth_or_routing",
        description="Diagnose authentication, profile, or routing issues",
        tags={"auth", "routing", "troubleshooting"},
        meta={"version": "0.2", "owner": "ads-platform"},
        task=False,
    )
    def troubleshoot_auth_or_routing_prompt() -> str:
        auth_step = (
            "1) Check OAuth state:\n   - Tool: check_oauth_status\n"
            if provider_type == "direct"
            else "1) Check active identity:\n"
            "   - Tool: get_active_identity\n"
            "   - Optional: list_identities if you need to inspect available identities\n"
        )
        return (
            "Goal: Diagnose authentication, profile, or routing issues on the utility-only server.\n"
            "Steps for the model:\n"
            f"{auth_step}"
            "2) Check active profile:\n"
            "   - Tool: get_active_profile\n"
            "3) Check routing state:\n"
            "   - Tool: get_routing_state\n"
            "4) If needed, update the region or profile:\n"
            "   - Tool: set_region\n"
            "   - Tool: set_active_profile\n"
            "Return: The likely issue, the current auth/profile/routing state, and the next action."
        )

    @server.prompt(
        name="setup_region",
        description="Configure region for API routing",
        tags={"region", "routing"},
        meta={"version": "0.2", "owner": "ads-platform"},
        task=False,
    )
    def setup_region_prompt(target_region: str) -> str:
        return (
            f"Goal: Configure API routing for region '{target_region}'.\n"
            "Steps for the model:\n"
            "1) Set the target region:\n"
            f"   - Tool: set_region\n"
            f"   - Parameter: region_code = '{target_region}'\n"
            "2) Verify configuration:\n"
            "   - Tool: get_region\n"
            "   - Tool: get_routing_state\n"
            "Return: Current routing configuration and validation results."
        )
