---
name: git-discipline
description: REQUIRED before and after ANY file creation or modification. This skill must be followed whenever you write, edit, delete, or rename any file. Non-negotiable in multi-agent workflows.
---

# Git Discipline — Mandatory for All File Changes

**STOP. If you are about to create, modify, or delete any file, these rules are mandatory. Your task is not complete until your changes are committed.**

## Pre-flight (before every file change)

Run this before you touch any file:

```bash
git status
git diff --name-only
```

If any files are modified that are NOT part of your current task, do not touch those files. They belong to another agent.

## After EVERY file write

Immediately after writing or modifying any file, before doing anything else:

```bash
git add <only the specific files you changed>
git commit -m "[role] short description"
```

Use the role prefix that matches your function:
- `[spec]` — specification, planning, design
- `[review]` — code review, feedback, corrections
- `[impl]` — implementation, feature code
- `[fix]` — bug fixes

**Never use `git add .` or `git add -A`.** Only stage files you personally changed.

## Rules

1. **One logical change = one commit.** Do not continue to the next change until the current one is committed.
2. **Your task is incomplete if changes are uncommitted.** Finishing the code is not finishing the task. The commit is part of the task.
3. **Do not stage or commit files you did not change.** If `git status` shows changes you don't recognize, leave them alone.
4. **If you hit a conflict or error on commit, stop and report it.** Do not resolve conflicts from other agents.
5. **Check before, commit after. Every time. No exceptions.**