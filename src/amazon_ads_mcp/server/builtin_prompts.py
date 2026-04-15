"""Built-in prompts for the stripped utility-only server."""

from typing import TYPE_CHECKING

from ..auth.manager import get_auth_manager

if TYPE_CHECKING:
    from fastmcp import FastMCP


async def register_all_builtin_prompts(server: "FastMCP") -> None:
    """Register the retained built-in prompts."""

    auth_mgr = get_auth_manager()
    provider_type = getattr(getattr(auth_mgr, "provider", None), "provider_type", None)
    profile_recovery_prompt = (
        "auth_profile_setup or troubleshoot_auth_or_routing"
        if provider_type == "direct"
        else "troubleshoot_auth_or_routing"
    )

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

    @server.prompt(
        name="sp_bid_optimization",
        description="Guide Sponsored Products bid optimization with the supported tool sequence",
        tags={"sponsored-products", "bids", "workflow"},
        meta={"version": "0.1", "owner": "ads-platform"},
        task=False,
    )
    def sp_bid_optimization_prompt() -> str:
        return (
            "Goal: Optimize Sponsored Products keyword bids with justified, bounded changes.\n"
            "Steps for the model:\n"
            "1) Verify execution context before any Sponsored Products action:\n"
            "   - Tool: get_routing_state\n"
            "   - Tool: get_active_profile\n"
            "   - If the active region is missing, stop clearly and use setup_region before continuing\n"
            f"   - If the active profile is missing or auth is not ready, stop clearly and use {profile_recovery_prompt}\n"
            "2) Scope the workflow to the campaigns you intend to review:\n"
            "   - Optional Tool: list_campaigns\n"
            "3) Read keyword performance for one reporting window:\n"
            "   - Tool: get_keyword_performance\n"
            "4) Decide whether each keyword should receive an increase, decrease, or no change:\n"
            "   - Base every action on the fetched performance data\n"
            "   - Keep bid adjustments bounded and explain the rationale for each change\n"
            "5) Apply only the approved bid updates:\n"
            "   - Tool: adjust_keyword_bids\n"
            "6) Return a final summary:\n"
            "   - Include execution-context verification, campaigns reviewed, bid changes applied or recommended, and any keywords left unchanged with reasons."
        )

    @server.prompt(
        name="sp_search_term_harvesting",
        description="Guide Sponsored Products search term harvesting and negation decisions",
        tags={"sponsored-products", "search-terms", "workflow"},
        meta={"version": "0.1", "owner": "ads-platform"},
        task=False,
    )
    def sp_search_term_harvesting_prompt() -> str:
        return (
            "Goal: Harvest Sponsored Products search terms into manual keywords or negatives using the supported tools.\n"
            "Steps for the model:\n"
            "1) Verify execution context before any Sponsored Products action:\n"
            "   - Tool: get_routing_state\n"
            "   - Tool: get_active_profile\n"
            "   - If the active region is missing, stop clearly and use setup_region before continuing\n"
            f"   - If the active profile is missing or auth is not ready, stop clearly and use {profile_recovery_prompt}\n"
            "2) Scope the campaigns you want to inspect:\n"
            "   - Optional Tool: list_campaigns\n"
            "3) Read search term performance for one reporting window:\n"
            "   - Tool: get_search_term_report\n"
            "4) Classify each relevant term into harvest, negate, or leave unchanged:\n"
            "   - Use the report metrics plus the existing manual and negative targeting context\n"
            "   - Explain why each term should be added, negated, or left untouched\n"
            "5) Apply only supported keyword mutations:\n"
            "   - Tool: add_keywords for harvest candidates\n"
            "   - Tool: negate_keywords for negation candidates\n"
            "6) Return a final summary:\n"
            "   - Include execution-context verification, harvested terms, negated terms, and terms left unchanged with reasons."
        )
