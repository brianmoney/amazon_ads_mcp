"""Server builder module for creating a utility-only MCP server."""

import logging
from typing import Optional

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware

from .. import __version__
from ..auth.manager import get_auth_manager
from ..config.settings import settings
from ..middleware.authentication import (
    AuthSessionStateMiddleware,
    create_auth_middleware,
    create_openbridge_config,
)

try:
    from ..middleware.oauth import create_oauth_middleware
except ImportError:
    create_oauth_middleware = None
from ..utils.header_resolver import HeaderNameResolver
from ..utils.http_client import AuthenticatedClient
from ..utils.media import MediaTypeRegistry
from ..utils.region_config import RegionConfig

logger = logging.getLogger(__name__)


class ServerBuilder:
    """Builder class for creating configured MCP servers."""

    def __init__(self, lifespan=None):
        """Initialize the server builder.

        :param lifespan: Optional async context manager for server lifespan.
                        If provided, handles startup/shutdown logic.
        :type lifespan: Optional[Callable[[], AsyncContextManager]]
        """
        # Parser flag will be set at runtime in main(), not at import time
        self.server: Optional[FastMCP] = None
        self.lifespan = lifespan  # Server lifespan context manager
        self.auth_manager = get_auth_manager()
        self.media_registry = MediaTypeRegistry()
        self.header_resolver = HeaderNameResolver()

    async def build(self) -> FastMCP:
        """Build and configure the MCP server."""

        # Ensure default identity is loaded if configured
        await self._setup_default_identity()

        # Create the main server
        self.server = await self._create_main_server()

        # Setup middleware
        await self._setup_middleware()

        # Setup HTTP client
        self.client = await self._setup_http_client()

        # Setup built-in tools
        await self._setup_builtin_tools()

        # Setup Sponsored Products tools
        await self._setup_sp_tools()

        # Setup Sponsored Display tools
        await self._setup_sd_tools()

        # Strip outputSchema from all registered tools (saves ~3K tokens)
        await self._strip_output_schemas()

        # Setup built-in prompts
        await self._setup_builtin_prompts()

        # Setup OAuth callback route for HTTP transport
        await self._setup_oauth_callback()

        # Setup health check endpoint for container orchestration
        await self._setup_health_check()

        return self.server

    async def _setup_default_identity(self):
        """Setup default identity if configured."""
        if hasattr(self.auth_manager, "_default_identity_id"):
            await self.auth_manager.set_active_identity(
                self.auth_manager._default_identity_id
            )

    async def _create_main_server(self) -> FastMCP:
        """Create the main FastMCP server instance.

        :return: Main server instance
        :rtype: FastMCP
        """
        # Create server with appropriate configuration
        # Include lifespan if provided for clean startup/shutdown handling
        server = FastMCP(
            "Amazon Ads MCP Server",
            version=__version__,
            lifespan=self.lifespan,
        )

        # Setup server-side sampling handler if enabled
        if settings.enable_sampling:
            try:
                from .sampling_handler import create_sampling_handler

                # Create the sampling handler
                sampling_handler = create_sampling_handler()

                if sampling_handler:
                    # Use the sampling wrapper instead of private attribute
                    from ..utils.sampling_wrapper import (
                        configure_sampling_handler,
                    )

                    configure_sampling_handler(sampling_handler)
                    logger.info("Server-side sampling handler configured via wrapper")
                else:
                    logger.info(
                        "Server-side sampling not configured (missing config or disabled)"
                    )

            except Exception as e:
                logger.error(f"Failed to setup sampling handler: {e}")
        else:
            logger.info("Sampling is disabled in settings")

        return server

    async def _setup_middleware(self):
        """Setup server middleware."""
        middleware_list = []

        # Error callback for logging
        def error_callback(error: Exception, context=None) -> None:
            logger.error(f"Tool execution error: {type(error).__name__}: {error}")

        # Add ErrorHandlingMiddleware FIRST to catch all errors from other middleware/tools
        # Production config: no tracebacks exposed, consistent error transformation
        error_middleware = ErrorHandlingMiddleware(
            include_traceback=False,  # Don't expose internal details
            transform_errors=True,  # Provide consistent error responses
            error_callback=error_callback,  # Log errors for debugging
        )
        middleware_list.append(error_middleware)
        logger.info("Added ErrorHandlingMiddleware for consistent error handling")

        # Persist auth/profile ContextVar state across MCP tool calls for all auth modes.
        middleware_list.append(AuthSessionStateMiddleware())
        logger.info("Added AuthSessionStateMiddleware")

        # Add response caching middleware (security-aware whitelist)
        if settings.enable_response_caching:
            from ..middleware.caching import create_caching_middleware

            caching_middleware = create_caching_middleware()
            middleware_list.append(caching_middleware)
            logger.info("Added ResponseCachingMiddleware with security-aware whitelist")

        # Add sampling middleware if configured
        from ..utils.sampling_wrapper import get_sampling_wrapper

        wrapper = get_sampling_wrapper()
        if wrapper.has_handler():
            from ..middleware.sampling import create_sampling_middleware

            sampling_middleware = create_sampling_middleware()
            if sampling_middleware:
                middleware_list.append(sampling_middleware)
            logger.info("Added server-side sampling middleware")

        # Add OpenBridge middleware if using OpenBridge auth
        provider_type = getattr(self.auth_manager.provider, "provider_type", None)
        if provider_type == "openbridge":
            ob_config = create_openbridge_config()
            auth_middlewares = create_auth_middleware(
                ob_config, auth_manager=self.auth_manager
            )
            # create_auth_middleware returns a list, so extend instead of append
            middleware_list.extend(auth_middlewares)
            logger.info(
                f"Added {len(auth_middlewares)} OpenBridge authentication middleware components"
            )

        # Add OAuth middleware if credentials are available
        if create_oauth_middleware and all(
            [
                settings.oauth_client_id,
                settings.oauth_client_secret,
                settings.oauth_redirect_uri,
            ]
        ):
            oauth_middleware = create_oauth_middleware()
            middleware_list.append(oauth_middleware)
            logger.info("Added OAuth middleware for web authentication")

        # Apply middleware to server
        for middleware in middleware_list:
            self.server.middleware.append(middleware)

    async def _setup_http_client(self) -> AuthenticatedClient:
        """Setup the authenticated HTTP client.

        :return: Configured HTTP client
        :rtype: AuthenticatedClient
        """
        # Auth-aware base URL selection

        # Determine base URL based on auth provider type
        if self.auth_manager and hasattr(self.auth_manager.provider, "provider_type"):
            provider_type = self.auth_manager.provider.provider_type

            if provider_type == "openbridge":
                # For OpenBridge: Default to NA at startup
                # The real region will be determined from the identity at request time
                region = "na"
                logger.info(
                    "OpenBridge: Using default NA base URL at startup (per-request routing will override based on identity)"
                )
            else:
                # For Direct auth: use configured region from settings
                region = settings.amazon_ads_region
                logger.info(
                    f"Direct auth: Using configured region '{region}' from settings"
                )
        else:
            # Fallback to settings region if no auth manager
            region = settings.amazon_ads_region
            logger.warning(
                f"No auth manager available, using region '{region}' from settings"
            )

        base_url = RegionConfig.get_api_endpoint(region)

        import httpx

        return AuthenticatedClient(
            auth_manager=self.auth_manager,
            media_registry=self.media_registry,
            header_resolver=self.header_resolver,
            base_url=base_url,
            timeout=httpx.Timeout(
                # Allow longer timeouts for Amazon Ads API
                connect=10.0,  # Connection timeout
                read=60.0,  # Read timeout for response
                write=10.0,  # Write timeout for request
                pool=10.0,  # Pool timeout
            ),
        )

    async def _setup_builtin_tools(self):
        """Setup built-in tools for the server."""
        from ..server.builtin_tools import register_all_builtin_tools

        await register_all_builtin_tools(self.server)

    async def _setup_sp_tools(self):
        """Setup Sponsored Products tools for the server."""
        from ..tools.sp import register_all_sp_tools

        await register_all_sp_tools(self.server)

    async def _setup_sd_tools(self):
        """Setup Sponsored Display tools for the server."""
        from ..tools.sd import register_all_sd_tools

        await register_all_sd_tools(self.server)

    async def _strip_output_schemas(self):
        """Strip outputSchema from all registered tools.

        MCP clients receive tool definitions including ``outputSchema`` on
        every ``tools/list`` call.  These response-shape schemas are rarely
        useful to Claude (it sees the actual return value) but can add
        thousands of tokens to the context window.

        This method nulls out ``output_schema`` on every tool registered
        on the main server, saving ~3K tokens for typical builtin tool
        sets.
        """
        tools = await self.server.list_tools()
        stripped = 0
        for tool_info in tools:
            try:
                tool = await self.server.get_tool(tool_info.name)
                if tool and getattr(tool, "output_schema", None) is not None:
                    tool.output_schema = None
                    stripped += 1
            except Exception:
                # Skip tool entries that cannot be resolved by name.
                pass

        if stripped:
            logger.info(
                "Stripped outputSchema from %d tools to reduce context usage",
                stripped,
            )

    async def _setup_builtin_prompts(self):
        """Setup built-in prompts for the server."""
        from ..server.builtin_prompts import register_all_builtin_prompts

        await register_all_builtin_prompts(self.server)

    async def _setup_oauth_callback(self):
        """Setup OAuth callback route for HTTP transport."""
        # Only register OAuth callback route for HTTP transport
        # Check if server has custom_route method (HTTP transport)
        if hasattr(self.server, "custom_route"):
            import httpx
            from starlette.requests import Request
            from starlette.responses import HTMLResponse

            @self.server.custom_route("/auth/callback", methods=["GET"])
            async def oauth_callback(request: Request):
                """Handle OAuth callback from Amazon with secure state validation."""
                from ..auth.oauth_state_store import get_oauth_state_store

                code = request.query_params.get("code")
                state = request.query_params.get("state")
                scope = request.query_params.get("scope")
                error = request.query_params.get("error")
                error_description = request.query_params.get("error_description")

                # Handle OAuth errors from Amazon
                if error:
                    logger.error(f"OAuth error: {error} - {error_description}")
                    # Don't expose internal error details in HTML
                    from .html_templates import get_error_html

                    html = get_error_html(
                        title="Authorization Failed",
                        message="The authorization request could not be completed.",
                    )
                    return HTMLResponse(html, status_code=400)

                # Validate required parameters
                if not code or not state:
                    logger.error("Missing code or state in OAuth callback")
                    from .html_templates import get_missing_params_html

                    html = get_missing_params_html()
                    return HTMLResponse(html, status_code=400)

                # Extract user agent and IP for validation
                user_agent = request.headers.get("user-agent")
                ip_address = request.client.host if request.client else None

                logger.info(
                    f"OAuth callback received: code=[REDACTED], state=[REDACTED], scope={scope}"
                )

                try:
                    # Validate state with secure store
                    state_store = get_oauth_state_store()
                    is_valid, error_message = state_store.validate_state(
                        state=state,
                        user_agent=user_agent,
                        ip_address=ip_address,
                    )

                    if not is_valid:
                        logger.warning(f"Invalid OAuth state: {error_message}")
                        from .html_templates import get_validation_error_html

                        html = get_validation_error_html()
                        return HTMLResponse(html, status_code=403)

                    # State is valid, proceed with token exchange
                    token_url = RegionConfig.get_oauth_endpoint(
                        settings.amazon_ads_region
                    )

                    # Use explicit timeout for OAuth token exchange
                    timeout = httpx.Timeout(
                        connect=10.0, read=30.0, write=10.0, pool=10.0
                    )
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(
                            token_url,
                            data={
                                "grant_type": "authorization_code",
                                "code": code,
                                "redirect_uri": settings.resolved_oauth_redirect_uri,
                                "client_id": settings.ad_api_client_id,
                                "client_secret": settings.ad_api_client_secret,
                            },
                        )

                    if response.status_code == 200:
                        tokens = response.json()

                        # Store tokens securely
                        try:
                            from datetime import datetime, timedelta, timezone

                            from ..auth.secure_token_store import (
                                get_secure_token_store,
                            )

                            secure_store = get_secure_token_store()

                            if "refresh_token" in tokens:
                                secure_store.store_token(
                                    token_id="oauth_refresh_token",
                                    token_value=tokens["refresh_token"],
                                    token_type="refresh",
                                    expires_at=datetime.now(timezone.utc)
                                    + timedelta(days=365),
                                    metadata={"scope": tokens.get("scope")},
                                )

                            if "access_token" in tokens:
                                secure_store.store_token(
                                    token_id="oauth_access_token",
                                    token_value=tokens["access_token"],
                                    token_type="access",
                                    expires_at=datetime.now(timezone.utc)
                                    + timedelta(seconds=tokens.get("expires_in", 3600)),
                                    metadata={
                                        "token_type": tokens.get("token_type", "Bearer")
                                    },
                                )

                            logger.info("Stored tokens in secure token store")
                        except Exception as e:
                            logger.error(f"Failed to store tokens securely: {e}")
                            # Don't expose internal error details
                            from .html_templates import (
                                get_token_storage_error_html,
                            )

                            html = get_token_storage_error_html()
                            return HTMLResponse(html, status_code=500)

                        # Store in auth manager if available
                        if self.auth_manager:
                            from datetime import datetime, timedelta, timezone

                            from ..auth.token_store import TokenKind

                            # Store refresh token
                            if "refresh_token" in tokens:
                                await self.auth_manager.set_token(
                                    provider_type="direct",
                                    identity_id="direct-auth",
                                    token_kind=TokenKind.REFRESH,
                                    token=tokens["refresh_token"],
                                    expires_at=datetime.now(timezone.utc)
                                    + timedelta(days=365),
                                    metadata={},
                                )

                            # Store access token
                            expires_at = datetime.now(timezone.utc) + timedelta(
                                seconds=tokens.get("expires_in", 3600)
                            )
                            await self.auth_manager.set_token(
                                provider_type="direct",
                                identity_id="direct-auth",
                                token_kind=TokenKind.ACCESS,
                                token=tokens["access_token"],
                                expires_at=expires_at,
                                metadata={"token_type": "Bearer"},
                            )

                            logger.info("Stored OAuth tokens in auth manager")

                        # Success response
                        from .html_templates import get_success_html

                        html = get_success_html()
                        return HTMLResponse(html)
                    else:
                        # Error response
                        error_msg = response.text
                        logger.error(
                            f"Token exchange failed: {response.status_code} - {error_msg}"
                        )

                        from .html_templates import (
                            get_token_exchange_error_html,
                        )

                        html = get_token_exchange_error_html()
                        return HTMLResponse(html, status_code=400)

                except Exception as e:
                    logger.error(f"OAuth callback error: {e}")
                    # Don't expose internal exception details
                    from .html_templates import get_server_error_html

                    html = get_server_error_html()
                    return HTMLResponse(html, status_code=500)

            logger.info("Registered OAuth callback route at /auth/callback")

    async def _setup_health_check(self):
        """Register /health endpoint for container orchestration.

        Returns 200 with basic server info. Used by load balancers,
        Cloudflare Containers, Kubernetes probes, etc.
        """
        if not hasattr(self.server, "custom_route"):
            return

        from starlette.requests import Request
        from starlette.responses import JSONResponse

        @self.server.custom_route("/health", methods=["GET"])
        async def health_check(request: Request) -> JSONResponse:
            return JSONResponse(
                {
                    "status": "healthy",
                    "service": "amazon-ads-mcp",
                    "version": __version__,
                }
            )
