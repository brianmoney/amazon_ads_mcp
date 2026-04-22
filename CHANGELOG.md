# Changelog

All notable changes to Amazon Ads MCP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Purpose-built Sponsored Products tools: `list_campaigns`, `get_keyword_performance`,
  `get_search_term_report`, `sp_report_status`, `adjust_keyword_bids`, `add_keywords`,
  `negate_keywords`, `pause_keywords`
- Shared async report lifecycle helper (`report_helper.py`) used by SP read tools
- Report resumability: `resume_from_report_id` parameter on `get_keyword_performance` and
  `get_search_term_report` to restart polling from a known report ID
- `sp_report_status` tool for checking the lifecycle state of an in-progress report
- Workflow prompts: `sp_bid_optimization` and `sp_search_term_harvesting`
- Clean `ServerBuilder` class with explicit SP tool registration hook
- Docker direct-auth workflow: source-built compose, `.env.example` with direct-auth defaults

### Changed
- Replaced generated OpenAPI tool catalog with 8 purpose-built Sponsored Products tools
- Rewrote `server_builder.py` as a clean `ServerBuilder` class
- Bounded SP report polling: non-zero initial interval, exponential backoff with jitter
- Raised `get_search_term_report` default timeout to 120 seconds
- Updated `docker-compose.yaml` and `.env.example` to default to direct Amazon Ads auth

### Removed
- OpenAPI-generated API tools and resource mounting (`dist/openapi/resources/`)
- OpenAPI helper modules and sidecar transforms (`openapi_utils.py`, `sidecar_loader.py`)
- Download tools and HTTP file download routes
- Code mode and progressive disclosure support
- Obsolete AMC, DSP, Stores, and generated API response model modules
- `AMAZON_AD_API_PACKAGES` namespace allowlist (was part of removed OpenAPI machinery)

### Security
- Secure token storage implementation with Fernet symmetric encryption
- OAuth state management with CSRF protection (user-agent + IP validation)
- Environment-based credential handling; token persistence disabled by default
- Per-request ContextVar isolation for OpenBridge refresh tokens (prevents cross-client cache leakage)
- Fingerprinted token cache for OpenBridge (SHA-256 keyed, LRU-bounded at 32 entries)

## Version History

This changelog will be automatically updated by our CI/CD pipeline when new releases are created.

---

*Note: Releases are automatically generated based on conventional commit messages:*
- `feat:` triggers minor version bump
- `fix:` triggers patch version bump
- `BREAKING CHANGE:` or `feat!:` triggers major version bump
