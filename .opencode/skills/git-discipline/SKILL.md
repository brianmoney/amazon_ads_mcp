---
name: git-discipline
description: Git commit discipline for multi-agent workflows sharing a single worktree. Use whenever making file changes in a project where multiple agents may be working concurrently.
---

# Git Discipline for Concurrent Agents

Multiple agents may be working in this repo simultaneously in the same worktree. Follow these rules to avoid conflicts and lost work.

## Before starting any file changes

1. Run `git status` to see what's already staged or modified.
2. If there are uncommitted changes from another agent, do NOT touch those files. Work around them or wait.
3. Run `git diff --name-only` to see exactly which files are dirty.

## While working

- Only modify files directly related to your current task.
- Avoid modifying files that show up as already changed in `git status`.
- If you must edit a file another agent has modified, commit your other work first, then coordinate.

## After completing each logical unit of work

Commit immediately. Do not batch multiple logical changes into one commit.

1. Stage only the files you changed: `git add <specific files>` — never `git add .` or `git add -A`.
2. Write a commit message prefixed with your role in brackets:
   - `[spec]` for specification/planning work
   - `[review]` for review feedback and fixes
   - `[impl]` for implementation work
   - `[fix]` for bug fixes identified during review
3. Commit format: `[role] short description of the single logical change`
4. Example: `[impl] add user authentication endpoint`

## Conflict prevention

- Keep changes small and focused. One logical change per commit.
- If `git status` shows unexpected changes you didn't make, do not stage them. Leave them for the agent that owns them.
- If you encounter a merge conflict or staged files you don't recognize, stop and report the situation rather than resolving blindly.

## What counts as "one logical change"

- Adding or modifying a single feature or function
- Updating a spec or plan document
- Writing or updating a review
- Fixing a single issue identified in review
- Updating tests for a single change

If you're unsure whether to commit, commit. Small commits are always safer than large ones in a concurrent workflow.