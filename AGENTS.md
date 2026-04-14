# Amazon Ads MCP Development Guidelines

> **Audience**: LLM-driven engineering agents and human developers

Amazon Ads MCP is in the middle of an OpenSpec-driven transition. The current server is utility-only: it retains authentication, profile management, region routing, OAuth, sampling, and HTTP client behavior, and the legacy OpenAPI-generated tool catalog has been removed. The active `openspec/changes/purpose-built-sp-tools/` meta change is rebuilding a narrow Sponsored Products tool surface in a controlled sequence.

## OpenSpec Workflow

This project uses OpenSpec for specification-driven development. All feature work follows the spec-implement-review cycle defined by OpenSpec.

- Start from the active change under `openspec/changes/<change-name>/`
- Keep proposal, design, and tasks aligned with implementation status
- Prefer small, sequential sub-changes that leave the repo runnable
- Do not implement feature work outside an approved OpenSpec change unless the task is clearly a small fix, docs-only update, or repo maintenance

## Active Meta Change

The active meta task is `openspec/changes/purpose-built-sp-tools/`.

- Current state: the `strip-openapi-machinery` sub-change is complete, so the checked-in runtime remains utility-only
- Next sub-changes: `rewrite-server-builder`, `sp-read-tools`, `sp-write-tools`, and `sp-workflow-prompts`
- Target end state: replace the removed OpenAPI surface with 7 purpose-built Sponsored Products tools and 2 workflow prompts
- Preserve unchanged behavior in auth, token management, HTTP client, profile selection, region routing, OAuth, sampling, and server startup plumbing
- Do not reintroduce generic OpenAPI mounting, generated tool catalogs, download routes, or code mode unless a future approved spec explicitly requires it

## Git Discipline (Required)

Multiple agents operate concurrently in this worktree. You MUST follow the `git-discipline` skill for all file changes.

- Check `git status` before starting work
- Do not touch files modified by another agent
- If you encounter unexpected changes or conflicts, stop and report rather than resolving on your own
- Commit after every logical unit of work; do not accumulate uncommitted changes
- Stage only your own files with `git add <specific files>`; never use `git add .` or `git add -A`
- Prefix commits with your role: `[spec]`, `[review]`, `[impl]`, or `[fix]`

## Do This First

- Ensure Python >=3.10 and `uv` are installed
- Run `uv sync`
- Start the server with `docker-compose up -d`
- Connect Claude to the MCP server over HTTP:
  - `claude mcp add amazon-ads-mcp -- python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080`
- Verify with `claude mcp list`

## Validation

Run focused validation for each logical unit before committing. Run the full validation suite in order before handoff, review, or merge.

```bash
uv run ruff check --fix
uv run pytest
docker build -t amazon-ads-mcp .
```

All three must pass for a completed change. When working through the `purpose-built-sp-tools` sub-changes, keep the repo runnable after each step and validate aggressively after deletions or import-graph changes.

## Current Runtime Surface

The retained server surface currently includes:

- Auth providers and token management
- OAuth callback flow and OAuth tools
- Profile selection and bounded profile listing tools
- Region selection and routing inspection tools
- Sampling middleware and sampling test tool
- HTTP client, middleware, and startup plumbing

The removed surface includes:

- OpenAPI resource mounting
- Generated API tools
- `dist/openapi/resources/`
- OpenAPI sidecars and transforms
- Download tools and file download routes
- Code mode and progressive disclosure

The active OpenSpec change is expected to add, in sequence:

- `tools/sp/` with 7 purpose-built Sponsored Products tools
- Shared async report helper(s) used internally by SP read tools
- 2 MCP workflow prompts for bid optimization and search term harvesting

## Editing Guidance

- Keep changes focused and minimal
- Preserve retained auth, profile, region, OAuth, sampling, and HTTP client behavior
- Keep `purpose-built-sp-tools` work aligned with its sub-change ordering
- Do not widen scope into unrelated refactors while advancing an OpenSpec change
- Update tests and docs in the same change when the runtime surface changes
- Do not restore deleted OpenAPI/download/code-mode machinery as compatibility shims

## Repository Areas

| Path | Purpose |
| --- | --- |
| `openspec/changes/` | OpenSpec change proposals, designs, and task tracking |
| `src/amazon_ads_mcp/server/` | MCP server bootstrap, built-in utility tools, and prompt registration |
| `src/amazon_ads_mcp/auth/` | Authentication providers and token handling |
| `src/amazon_ads_mcp/tools/` | Retained utility tools; `tools/sp/` is the planned home for purpose-built SP tools |
| `src/amazon_ads_mcp/models/` | Pydantic models for retained utility/auth flows and future SP models |
| `src/amazon_ads_mcp/middleware/` | Authentication, OAuth, caching, and sampling middleware |
| `src/amazon_ads_mcp/utils/` | HTTP client, routing, security, and support utilities |
| `tests/` | Pytest suite |

## Common Commands

```bash
git status --short --branch
uv sync
uv run ruff check --fix
uv run pytest
docker-compose up -d
docker build -t amazon-ads-mcp .
uv run python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
```

## Guardrails

- Do not push directly to `main`
- Do not log secrets or tokens
- Do not touch another agent's modified files
- Do not widen scope into unrelated refactors
- Do not restore deleted OpenAPI/download/code-mode machinery as compatibility shims
