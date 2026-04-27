## OpenSpec + Git discipline

This project uses OpenSpec with `/opsx-ff`, `/opsx-apply`, `/opsx-verify`, and `/opsx-archive`.

Agents working in `amazon-ads-mcp` must adhere to the OpenSpec workflow. Do not bypass proposal, implementation, verification, or archive steps for work that belongs in OpenSpec.

### Repo map

This repo layout is easy to misread. Treat these paths as different Git owners:

- `amazon-ads-mcp/` is the public code repo.
- `amazon-ads-mcp/internal/` is a Git submodule checkout of the private repo `amazon-ads-mcp-private`.
- `amazon-ads-mcp/openspec/` is a symlink to `amazon-ads-mcp/internal/openspec/`.
- Editing `openspec/...` changes files owned by the private `internal/` repo, not by the public parent repo.
- The parent repo never contains the OpenSpec file contents directly. It only records the `internal` gitlink SHA after the submodule commit.

If this distinction is fuzzy, agents will stage the wrong repo. Always check both repos before and after OpenSpec work:

```bash
git status --short
git -C internal status --short
```

### Core rule

Work in place from the main project directory. Do not create per-change branches or worktrees unless the user explicitly asks for them.

- Use explicit path staging and commit only the current OpenSpec change.
- A dirty repo is not by itself a blocker. Ignore unrelated uncommitted files and leave them unstaged.
- Stop only if unrelated changes overlap the exact paths you need for the current change or make validation ambiguous.
- Keep the OpenSpec commit in `internal/` and the matching `internal` gitlink commit in the parent repo paired.

### Naming convention

Use the OpenSpec change id consistently:

```bash
<change-id>
spec/<change-id>
```

Example:

```bash
add-user-settings-panel
spec/add-user-settings-panel
```

The `spec/<change-id>` tag is a local marker for the committed spec snapshot. Do not push tags unless the user explicitly asks.

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
- When OpenSpec files change, commit in `internal/` first for the actual OpenSpec files, then reuse the same message in the parent repo for the matching `internal` gitlink update.
- `/opsx-ff` must end with the `spec(<change-id>): define OpenSpec change` commit sequence.
- `/opsx-archive` must end with the `archive(<change-id>): archive completed OpenSpec change` commit sequence.

---

## `/opsx-ff` handoff contract

1. Create all apply-ready artifacts under `openspec/changes/<change-id>/`.
2. Commit those artifacts in `internal/` with `spec(<change-id>): define OpenSpec change`.
3. Create or move the local `spec/<change-id>` tag to that `internal/` commit.
4. Commit the parent `internal` gitlink update with the same message.
5. Create or move the local `spec/<change-id>` tag in the parent repo to the matching gitlink commit.
6. Hand off the change id. Implementation continues in the main repo, not in a separate worktree.

---

## `/opsx-ff` agent instructions

Run `/opsx-ff` from the main project directory.

The `/opsx-ff` agent may create or update files under:

```text
openspec/changes/<change-id>/
```

The visible `openspec/...` path resolves into `internal/openspec/...`, so the actual Git-tracked proposal files live in the private `internal/` submodule.

The `/opsx-ff` agent must not implement application code changes.

After creating the OpenSpec change, immediately commit only the proposal files for the current change. Do not stop just because other files are dirty; leave unrelated files unstaged.

```bash
git status --short
git -C internal status --short

git -C internal add -- openspec/changes/<change-id>
git -C internal diff --cached --name-only
git -C internal commit -m "spec(<change-id>): define OpenSpec change"
git -C internal tag -f "spec/<change-id>"

git add -- internal
git diff --cached --name-only
git commit -m "spec(<change-id>): define OpenSpec change"
git tag -f "spec/<change-id>"
```

Stop only if unrelated changes already touch `openspec/changes/<change-id>` or otherwise prevent a clean spec commit for the current change.

---

## `/opsx-apply` agent instructions

Run `/opsx-apply` from the main project directory.

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
- create extra branches or worktrees for the change

Before editing, inspect:

```bash
git status --short
git -C internal status --short
```

Unrelated dirty files are not an automatic blocker. Keep the current change scoped to its own files and do not stage or commit as part of `/opsx-apply`.

Before finishing, report:

```bash
git status --short
git diff --stat
git -C internal status --short
git -C internal diff --stat
```

---

## `/opsx-verify` agent instructions

Run `/opsx-verify` from the main project directory.

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

- OpenSpec validation fails
- relevant tests fail
- the implementation does not match the accepted OpenSpec change
- unrelated modified files overlap the paths needed for the current verification or make the result ambiguous

The verify agent must not commit unless explicitly instructed by the user.

---

## `/opsx-archive` agent instructions

Run `/opsx-archive` from the main project directory after verification succeeds.

Before archiving:

```bash
git status --short
git diff --name-only
openspec validate --strict
git -C internal status --short
git -C internal diff --name-only
```

After `/opsx-archive`, create the archive commit in place from the main project directory.

Use explicit paths. Do not use `git add .`.

Ignore unrelated dirty files and leave them unstaged. Only stop if they overlap files that belong to the current change.

Recommended flow:

```bash
git status --short
git -C internal status --short

# Stage and commit the OpenSpec archive files inside the internal submodule first.
git -C internal add -- openspec/specs/
git -C internal add -- openspec/changes/<change-id>
git -C internal diff --cached --name-only
git -C internal diff --cached --stat

openspec validate --strict

git -C internal commit -m "archive(<change-id>): archive completed OpenSpec change"

# Stage only parent-repo files belonging to the verified change plus the updated submodule pointer.
git add -- <verified-implementation-files>
git add -- internal

git diff --cached --name-only
git diff --cached --stat

openspec validate --strict

git commit -m "archive(<change-id>): archive completed OpenSpec change"
```

Before committing, confirm:

- all staged files belong to `<change-id>`
- OpenSpec validation passes
- relevant tests pass
- no unrelated changes are included in the staged set
- no secrets, generated junk, logs, local config, or build artifacts are staged

Do not push unless explicitly instructed.

---

## Staging discipline

Agents must use explicit staging.

Allowed:

```bash
git add -- path/to/file1 path/to/file2
git -C internal add -- openspec/changes/<change-id>
git -C internal add -- openspec/specs/
git add -- internal
git restore --staged -- path/to/file
git -C internal restore --staged -- path/to/file
```

Forbidden unless explicitly approved:

```bash
git add openspec/changes/<change-id>
git add openspec/specs/
git add .
git add -A
git add -u
git switch -c feature/<change-id>
git worktree add ../<change-id>
```

Before every commit, run:

```bash
git -C internal diff --cached --name-only
git diff --cached --name-only
```

If any staged file is unrelated to the current OpenSpec change, unstage it before committing.

For Git-related questions or non-routine Git operations, agents should consult the installed `git-workflow` skill. However, these instructions take precedence over the skill for this project's required OpenSpec workflow, submodule ownership rules, tag usage, staging rules, commit timing, and archive commits.

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
