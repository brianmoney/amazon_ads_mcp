
## Install The MCP Server: Choose your preferred installation method

### Path 1: Run with Python (Recommended for Development)

#### Prerequisites:
- Python 3.10 or higher
- Amazon Ads API access or an Ads API Partner Provider (e.g. OpenBridge)
- `uv` for dependency management (recommended)

#### Installation:

**Option A: Using uv (Recommended)**
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/KuudoAI/amazon-ads-mcp.git
cd amazon-ads-mcp

# Install dependencies with uv
uv venv
uv sync

# Run the server (HTTP transport)
uv run python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
```

**Option B: Using pip**
```bash
# Clone the repository
git clone https://github.com/KuudoAI/amazon-ads-mcp.git
cd amazon-ads-mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install from pyproject.toml
pip install .

# Run the server (HTTP transport)
python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
```

### Path 2: Run with Docker

#### Prerequisites:
- Docker with the `docker compose` plugin
- Amazon Ads API credentials (direct auth) or OpenBridge credentials

#### Installation:

```bash
# Clone the repository
git clone https://github.com/KuudoAI/amazon-ads-mcp.git
cd amazon-ads-mcp

# Copy the environment template
cp .env.example .env

# Edit .env for direct Amazon Ads auth
# Required:
#   AUTH_METHOD=direct
#   PORT=9080
#   AMAZON_AD_API_CLIENT_ID=...
#   AMAZON_AD_API_CLIENT_SECRET=...
#   AMAZON_AD_API_REFRESH_TOKEN=...

# Optional:
#   AMAZON_AD_API_PROFILE_ID=...
#   AMAZON_ADS_REGION=na
#   OAUTH_REDIRECT_URI=http://localhost:9080/auth/callback
#   AMAZON_ADS_TOKEN_PERSIST=true

# Build from the local repository context
docker compose build

# Start the server
docker compose up -d

# The server will be available at http://localhost:9080
# Check logs
docker compose logs -f amazon-ads-mcp

# Verify the container is healthy enough to serve HTTP
curl http://localhost:9080/health

# Stop the server
docker compose down
```

The default `docker-compose.yaml` workflow is source-built and direct-auth first. It publishes host port `9080` to container port `9080` and persists cache data under `/app/.cache`.

If you want bind mounts instead of named Docker volumes during local development, use:

```bash
docker compose -f docker-compose.local.yaml build
docker compose -f docker-compose.local.yaml up -d
```

That local compose file writes cache data to `./.cache`.

To switch Docker testing to OpenBridge, override the auth method and provide OpenBridge credentials:

```bash
AUTH_METHOD=openbridge OPENBRIDGE_REFRESH_TOKEN="your-openbridge-token" docker compose up -d
```

`AUTH_METHOD` is the documented selector. `AMAZON_ADS_AUTH_METHOD` remains supported as a legacy alias.

**Quick Docker Run (without compose):**
```bash
# Build the image
docker build -t amazon-ads-mcp .

# Run the container
docker run -d \
  --name amazon-ads-mcp \
  -p 9080:9080 \
  -e AUTH_METHOD=direct \
  -e AMAZON_AD_API_CLIENT_ID="your-client-id" \
  -e AMAZON_AD_API_CLIENT_SECRET="your-client-secret" \
  -e AMAZON_AD_API_REFRESH_TOKEN="your-refresh-token" \
  amazon-ads-mcp
```

---

## Authentication

### Direct Amazon Ads OAuth

Direct auth uses your own Amazon Ads API application (BYOA — Bring Your Own App). You need three credentials: a Client ID, a Client Secret, and a Refresh Token.

#### Step 1: Register an Amazon Developer Application

1. Sign in to the [Amazon Developer Console](https://developer.amazon.com/apps-and-games/console)
2. Create a new application (or use an existing one). This gives you a **Client ID** and **Client Secret** under the **Login with Amazon** section.
3. Under **Allowed Return URLs**, add your OAuth callback URL. For local use: `http://localhost:9080/auth/callback`
4. Ensure your application has access to the Amazon Advertising API. If you manage ads for your own accounts, your Amazon Ads account may qualify for [self-service API access](https://advertising.amazon.com/API/docs/en-us/get-started/first-steps). Agencies and tool providers should apply through the [Amazon Ads API Partner Program](https://advertising.amazon.com/API/docs/en-us/get-started/partner-program).

#### Step 2: Configure the Server with Your Client Credentials

Set at minimum the Client ID and Client Secret. The Refresh Token can be obtained via the built-in OAuth flow in the next step.

```bash
AUTH_METHOD=direct
AMAZON_AD_API_CLIENT_ID="amzn1.application-oa2-client.xxxxx"
AMAZON_AD_API_CLIENT_SECRET="your-client-secret"
OAUTH_REDIRECT_URI="http://localhost:9080/auth/callback"
```

Start the server:

```bash
uv run python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
```

#### Step 3: Run the Built-in OAuth Flow to Get a Refresh Token

The easiest way to obtain a Refresh Token is through the built-in `start_oauth_flow` MCP tool. Connect an MCP client (e.g. Claude Desktop) and ask it to run the tool:

```
Use the start_oauth_flow tool to authenticate with Amazon Ads
```

The tool generates an authorization URL and opens your browser. After you sign in and approve access, Amazon redirects to your callback URL. The server automatically exchanges the authorization code for tokens and stores them. The Refresh Token is persisted if `AMAZON_ADS_TOKEN_PERSIST=true`.

You can check status and refresh tokens manually using:
- `check_oauth_status` — verify the current auth state
- `refresh_oauth_token` — force a token refresh
- `clear_oauth_tokens` — remove stored tokens

#### Step 4: Set the Environment Variable (if bypassing the OAuth flow)

If you already have a Refresh Token from a previous authorization grant:

```bash
AMAZON_AD_API_REFRESH_TOKEN="Atzr|IwEB..."
```

The server will use this token directly on startup without requiring the OAuth flow. Note that Refresh Tokens expire if unused and must be re-obtained through the OAuth flow when that happens.

#### Optional Settings

```bash
# Set a default profile to avoid selecting one on each startup
AMAZON_AD_API_PROFILE_ID="1234567890"

# Region (na = North America, eu = Europe, fe = Far East)
AMAZON_ADS_REGION="na"

# Enable sandbox mode for testing (no real API charges)
AMAZON_ADS_SANDBOX_MODE=true

# Persist tokens to disk (encrypted; required to survive server restarts)
AMAZON_ADS_TOKEN_PERSIST=true
```

---

### OpenBridge

[OpenBridge](https://openbridge.com) is a multi-tenant identity broker for Amazon Ads. Use this auth method when your advertising accounts are managed through OpenBridge — you provide an OpenBridge Refresh Token instead of managing Amazon OAuth credentials yourself.

How it works:
1. The server exchanges your OpenBridge Refresh Token for a short-lived JWT via the OpenBridge auth API
2. That JWT is used to list your Amazon Ads remote identities (accounts)
3. Per-identity Amazon Ads bearer tokens are fetched on demand
4. Region routing is identity-controlled — each identity carries its own region

```bash
AUTH_METHOD=openbridge
OPENBRIDGE_REFRESH_TOKEN="your-openbridge-refresh-token"
```

`OPENBRIDGE_API_KEY` is accepted as a legacy alias for `OPENBRIDGE_REFRESH_TOKEN`.

In gateway or proxy deployments, the token can be passed per-request via the `X-Openbridge-Token` header (preferred) or `Authorization: Bearer` header rather than being set in the environment.

After the server starts, use `list_identities` to see available Amazon Ads accounts and `set_active_identity` to select one.

---

### Token Persistence

Token persistence is **disabled by default**. When enabled, tokens are **encrypted** using Fernet symmetric encryption (AES-128).

- **To enable**: Set `AMAZON_ADS_TOKEN_PERSIST=true`
- **Storage location**:
  - Docker: `/app/.cache/amazon-ads-mcp/tokens.json`
  - Local: `~/.amazon-ads-mcp/tokens.json`
- **Custom cache directory**: Set `AMAZON_ADS_CACHE_DIR=/path/to/cache`

**Security Requirements**:

For **Development/Local**:
- Machine-specific keys are automatically generated
- Install `cryptography`: `pip install cryptography`

For **Production**:
- **Required**: Set `AMAZON_ADS_ENCRYPTION_KEY` with a secure key
- Generate a key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Store the key securely (AWS Secrets Manager, HashiCorp Vault, etc.)
- Never commit encryption keys to version control

**Security Controls**:
- Missing `cryptography` library will refuse to persist tokens unless `AMAZON_ADS_ALLOW_PLAINTEXT_PERSIST=true` (not recommended)
- Invalid encryption keys trigger warnings and fallback to machine-derived keys
- Production environments (`ENV=production`) issue warnings when using machine-derived keys
