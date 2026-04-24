## OpenSpec + Git worktree discipline

This project uses OpenSpec with `/opsx-ff`, `/opsx-apply`, `/opsx-verify`, and `/opsx-archive`.

Agents working in `amazon-ads-mcp` must adhere to the OpenSpec workflow. Do not bypass proposal, implementation, verification, or archive steps for work that belongs in OpenSpec.

### Core rule

Each OpenSpec change gets its own Git branch and worktree.

- Planning starts in the main project directory.
- Implementation, verification, archive, and final commit happen in the change worktree.
- Do not run multiple OpenCode sessions against the same worktree for the same change.
- Never mix unrelated OpenSpec changes in one branch or one commit.

### OpenSpec path and submodule rule

In this repo, `openspec/` is a symlink to `internal/openspec/`.

- `internal/` is a Git submodule that points at the private repo.
- OpenSpec file contents are Git-tracked by the `internal/` repo, not by the parent repo.
- The parent repo only tracks the `internal` gitlink update after the submodule commit.
- Read or edit via `openspec/...` if convenient, but treat `internal/openspec/...` as the real Git-tracked path.
- Before any OpenSpec commit, inspect both `git status --short` and `git -C internal status --short`.
- Do not expect `git add openspec/...` in the parent repo to stage OpenSpec files. Use `git -C internal add ...` for OpenSpec files, then `git add internal` in the parent repo.
- Keep the parent repo branch/worktree and the `internal/` branch aligned to the same `<change-id>`.

### Naming convention

Use the OpenSpec change id consistently:

```bash
<change-id>
feature/<change-id>
../<change-id>
```

Example:

```bash
add-user-settings-panel
feature/add-user-settings-panel
../add-user-settings-panel
```

---

## Commit message discipline

Use Conventional Commit style.

Required lifecycle commit formats:

```text
spec(<change-id>): define OpenSpec change
archive(<change-id>): archive completed OpenSpec change
```

Allowed implementation commit formats, if explicitly requested by the user:

```text
feat(<change-id>): ...
fix(<change-id>): ...
refactor(<change-id>): ...
test(<change-id>): ...
docs(<change-id>): ...
chore(<change-id>): ...
```

Rules:

- The scope must be the OpenSpec `<change-id>`.
- Use lowercase commit types.
- Keep the first line under 100 characters.
- Do not use vague messages like `update`, `changes`, `fix stuff`, or `wip`.
- Do not commit unless the current role explicitly allows committing.
- When OpenSpec files change, use the lifecycle commit message in `internal/` for the actual OpenSpec files, then reuse the same message in the parent repo for the matching `internal` gitlink update.

---

## `/opsx-ff` agent instructions

Run `/opsx-ff` from the main project directory.

The `/opsx-ff` agent may create or update files under:

```text
openspec/changes/<change-id>/
```

The visible `openspec/...` path resolves into `internal/openspec/...`, so the actual Git-tracked proposal files live in the `internal/` submodule.

The `/opsx-ff` agent must not implement application code changes.

After creating the OpenSpec change, immediately commit only the new proposal files:

```bash
git status --short
git -C internal status --short
git -C internal switch -c feature/<change-id> || git -C internal switch feature/<change-id>
git -C internal add openspec/changes/<change-id>
git -C internal diff --cached --name-only
git -C internal commit -m "spec(<change-id>): define OpenSpec change"

git status --short
git add internal
git diff --cached --name-only
git commit -m "spec(<change-id>): define OpenSpec change"
```

Then create a dedicated implementation worktree:

```bash
git worktree add ../<change-id> -b feature/<change-id>
```

Then instruct the implementer to launch OpenCode from the worktree:

```bash
cd ../<change-id>
git submodule update --init --recursive internal
git -C internal switch -c feature/<change-id> || git -C internal switch feature/<change-id>
opencode
```

Stop if either `git status --short` or `git -C internal status --short` shows unrelated changes.

---

## `/opsx-apply` agent instructions

Run `/opsx-apply` only from the change worktree:

```bash
cd ../<change-id>
git submodule update --init --recursive internal
git -C internal switch -c feature/<change-id> || git -C internal switch feature/<change-id>
opencode
```

The apply agent may edit:

- implementation files required by the current OpenSpec change
- tests required by the current OpenSpec change
- OpenSpec task/status files for the current change

The apply agent must not:

- commit
- push
- archive
- rebase
- run destructive Git cleanup commands
- modify files unrelated to the current OpenSpec change

Before editing, inspect:

```bash
git status --short
git -C internal status --short
```

Before finishing, report:

```bash
git status --short
git diff --stat
git -C internal status --short
git -C internal diff --stat
```

---

## `/opsx-verify` agent instructions

Run `/opsx-verify` from the change worktree, not the main project directory.

Before verification:

```bash
git status --short
git diff --name-only
git diff --stat
git -C internal status --short
git -C internal diff --name-only
git -C internal diff --stat
```

Verify only the current OpenSpec change.

Required checks:

```bash
openspec validate --strict
```

Also run the relevant project checks, such as tests, linters, type checks, and build checks.

Stop if:

- unrelated modified files are present in either repo
- OpenSpec validation fails
- relevant tests fail
- the implementation does not match the accepted OpenSpec change

The verify agent must not commit unless explicitly instructed by the user.

---

## `/opsx-archive` agent instructions

Run `/opsx-archive` from the change worktree after verification succeeds.

Before archiving:

```bash
git status --short
git diff --name-only
openspec validate --strict
git -C internal status --short
git -C internal diff --name-only
```

After `/opsx-archive`, create the archive commit from the change worktree.

Use explicit paths. Do not use `git add .`.

Recommended flow:

```bash
git status --short
git -C internal status --short

# Stage and commit the OpenSpec archive files inside the internal submodule first.
git -C internal add openspec/specs/
git -C internal add openspec/changes/<change-id>
git -C internal diff --cached --name-only
git -C internal diff --cached --stat

openspec validate --strict

git -C internal commit -m "archive(<change-id>): archive completed OpenSpec change"

# Stage only parent-repo files belonging to the verified change plus the updated submodule pointer.
git add <verified-implementation-files>
git add internal

git diff --cached --name-only
git diff --cached --stat

openspec validate --strict

git commit -m "archive(<change-id>): archive completed OpenSpec change"
```

Before committing, confirm:

- all staged files belong to `<change-id>`
- OpenSpec validation passes
- relevant tests pass
- no unrelated changes are included
- no secrets, generated junk, logs, local config, or build artifacts are staged

Do not push unless explicitly instructed.

---

## Staging discipline

Agents must use explicit staging.

Allowed:

```bash
git add path/to/file1 path/to/file2
git -C internal add openspec/changes/<change-id>
git -C internal add openspec/specs/
git add internal
```

Forbidden unless explicitly approved:

```bash
git add openspec/changes/<change-id>
git add openspec/specs/
git add .
git add -A
git add -u
```

Before every commit, run:

```bash
git diff --cached --name-only
```

If any staged file is unrelated to the current OpenSpec change, unstage it before committing.

For Git-related questions or non-routine Git operations, agents should consult the installed `git-workflow` skill. However, these instruction takes precedence over the skill for this project’s required OpenSpec workflow, worktree usage, staging rules, commit timing, and archive commits. 

---

## Amazon Ads MCP repo context

This repo is a Python MCP server for Amazon Ads authentication, routing, profile and identity management, and a curated tool surface for Sponsored Products and Sponsored Display workflows.

### Repo identity and entrypoints

- The package and console script name is `amazon-ads-mcp`.
- The Python module path uses underscores: `amazon_ads_mcp`.
- The main entry point is `amazon_ads_mcp.server.mcp_server`.
- Run repo-local commands from the `amazon-ads-mcp/` root, not from the workspace wrapper directory.

Setup and local run commands:

```bash
uv sync
uv run python -m amazon_ads_mcp.server.mcp_server --transport http --port 9080
```

### Source of truth for server behavior

- Treat the accepted OpenSpec change as the planning source of truth for behavior changes.
- Treat `README.md` as the human-readable source of truth for the MCP surface exposed to clients.
- Treat the registration code as the executable source of truth for tools and prompts.
- When changing tool or prompt availability, verify the relevant registration files and update `README.md` when the user-facing surface changes.

Primary registration files:

```text
src/amazon_ads_mcp/server/builtin_tools.py
src/amazon_ads_mcp/tools/sp/__init__.py
src/amazon_ads_mcp/tools/sd/__init__.py
src/amazon_ads_mcp/server/builtin_prompts.py
```

Do not treat legacy OpenAPI-generated catalogs, download/export helpers, or code-mode helper surfaces as authoritative for the exposed MCP interface unless the accepted OpenSpec change explicitly says to revive or replace them.

### High-risk domains

- Authentication and routing logic are safety-critical in this repo.
- Supported auth modes are `direct` and `openbridge`; do not hardcode one path or break the other.
- Preserve per-request auth header propagation, active profile selection, active identity selection, and region resolution behavior unless the OpenSpec change explicitly modifies them.
- Prefer extending existing abstractions in `src/amazon_ads_mcp/auth/`, `src/amazon_ads_mcp/config/`, `src/amazon_ads_mcp/middleware/`, and `src/amazon_ads_mcp/server/` rather than duplicating header, token, or environment parsing in tool modules.

### Reporting and tool-surface expectations

- Sponsored Products and Sponsored Display report tools use async create-or-resume flows.
- Preserve resume and status semantics when touching report helpers or tool contracts.
- Do not introduce behavior that silently creates duplicate reports, removes resume support, or changes derived metrics/output shape without an accepted OpenSpec change and matching tests.

### Tests and validation for this repo

- Unit tests live under `tests/unit/` and integration tests live under `tests/integration/`.
- Prefer the narrowest relevant tests first for the slice you changed, then run the repo validation flow required before commit.
- If auth, routing, profile, identity, or middleware behavior changes, include targeted integration coverage when relevant.

Required repo validation order before commit:

```bash
uv run ruff check --fix
uv run pytest
docker build -t amazon-ads-mcp .
```

### Implementation guardrails

- Python 3.10+ is the project baseline.
- Keep typed function signatures intact; the repo is configured for strict typed definitions.
- Preserve the existing Black/isort style and 79-character line length.
- Never commit real Amazon Ads or OpenBridge credentials, refresh tokens, cached OAuth state, `.env` files, or local runtime cache data.

---

## Optional Git hooks

This project may use hooks to enforce basic safety checks.

Recommended hook location:

```bash
.githooks/
```

Enable once per clone:

```bash
git config core.hooksPath .githooks
```

### `.githooks/commit-msg`

```bash
#!/usr/bin/env bash
set -euo pipefail

msg_file="$1"
first_line="$(head -n1 "$msg_file")"

pattern='^(spec|archive|feat|fix|refactor|test|docs|chore)\([a-z0-9][a-z0-9-]*\): .{1,100}$'

if ! [[ "$first_line" =~ $pattern ]]; then
  echo "Invalid commit message:"
  echo "  $first_line"
  echo
  echo "Expected:"
  echo "  spec(<change-id>): define OpenSpec change"
  echo "  archive(<change-id>): archive completed OpenSpec change"
  echo "  feat(<change-id>): short description"
  exit 1
fi
```

### `.githooks/pre-commit`

```bash
#!/usr/bin/env bash
set -euo pipefail

staged_files="$(git diff --cached --name-only)"

if [[ -z "$staged_files" ]]; then
  echo "No staged files."
  exit 1
fi

for forbidden in ".env" ".env.local" "npm-debug.log" "yarn-error.log" "pnpm-debug.log"; do
  if echo "$staged_files" | grep -qx "$forbidden"; then
    echo "Refusing to commit forbidden file: $forbidden"
    exit 1
  fi
done

if echo "$staged_files" | grep -E '(^|/)(dist|build|coverage|node_modules|__pycache__)/' >/dev/null; then
  echo "Refusing to commit generated/build/cache files."
  echo "$staged_files" | grep -E '(^|/)(dist|build|coverage|node_modules|__pycache__)/'
  exit 1
fi

if command -v openspec >/dev/null 2>&1; then
  openspec validate --strict
fi
```

Make hooks executable:

```bash
chmod +x .githooks/commit-msg .githooks/pre-commit
```

---

## Forbidden Git commands without explicit user approval

Agents must not run:

```bash
git reset --hard
git clean -fd
git checkout .
git restore .
git rebase
git push --force
git push
```

Safe inspection commands are allowed:

```bash
git status --short
git diff
git diff --stat
git diff --name-only
git diff --cached --name-only
git log --oneline -n 10
git branch --show-current
git worktree list
```
