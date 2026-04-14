---
name: openspec-review-change
description: Thoroughly review an OpenSpec change before archive. Use when the user wants a final readiness review, wants to know whether a change is actually complete, needs a concise implementation handoff prompt for remaining gaps, or wants a go/no-go recommendation before `/opsx-archive`.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.1.1"
---

Review an OpenSpec change and decide whether it is ready to archive or needs more implementation work.

This is a decision skill, not just a checklist. Read the change artifacts, inspect the implementation, and end with a clear recommendation:
- **Archive recommended** when the change is substantively complete
- **Implementation prompt required** when important work is still missing or diverges from the change instructions

**Input**: Optionally specify a change name after `/opsx-review` (for example, `/opsx-review add-auth`). If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **If no change name provided, prompt for selection**

   Run `openspec list --json` to get available changes. Use the **AskUserQuestion tool** to let the user select.

   Show active changes only. Include the schema if available. Prefer showing changes that already have tasks or implementation progress.

   **IMPORTANT**: Do NOT guess or auto-select a change when multiple reasonable candidates exist.

2. **Check status to understand the workflow**

   ```bash
   openspec status --change "<name>" --json
   ```

   Parse the JSON to understand:
   - `schemaName`: the workflow being used
   - `artifacts`: which artifacts exist and whether they are `done`, `ready`, or blocked
   - Whether the change appears artifact-complete

3. **Load the implementation context**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   This returns the change directory, progress, tasks, and `contextFiles`.

   Read every available file in `contextFiles`. This usually includes proposal, specs, design, and tasks. If delta specs exist under `openspec/changes/<name>/specs/` and were not already listed, read them too.

4. **Build a concise understanding of the intended change**

   Extract and summarize:
   - The user-facing goal of the change
   - The capabilities or requirements it adds or modifies
   - The main design decisions or constraints
   - The implementation tasks that were supposed to be completed

   Keep this summary short. It should explain what the change was meant to accomplish before you judge the implementation.

5. **Review implementation completeness**

   Check the implementation against the artifacts.

   **Tasks**:
   - If `tasks.md` exists, count complete vs incomplete checkboxes
   - Treat unchecked tasks as missing unless the code clearly proves the task was already completed but not marked
   - If the code proves a task is done, note that the artifact is stale rather than calling the implementation missing

   **Requirements**:
   - For each requirement in delta specs, look for concrete implementation evidence in the codebase
   - Note the strongest evidence with file references
   - If a requirement has no convincing evidence, mark it as missing

   **Scenarios and tests**:
   - For each important scenario, check whether the code path exists
   - Check whether tests cover the expected behavior where tests are appropriate
   - Missing tests are usually a WARNING unless the change is test-heavy or the scenario is risky

6. **Review implementation quality and alignment**

   Assess how well the implementation matches the artifacts.

   **Design alignment**:
   - If `design.md` exists, compare implementation choices against its key decisions
   - Distinguish between acceptable simplification and actual divergence

   **Instruction alignment**:
   - Compare what the tasks and specs explicitly asked for against what was implemented
   - Call out partial implementations, missing edge cases, or behavior that solves a different problem than the artifact described

   **Project fit**:
   - Note obvious consistency issues with existing patterns, file placement, naming, or test strategy
   - Do not nitpick minor style issues unless they affect maintainability or confidence in the change

7. **Classify findings by decision impact**

   Use three levels:
   - **CRITICAL**: change is not ready to archive; requirements or tasks are materially incomplete; implementation contradicts the artifact intent
   - **WARNING**: core behavior appears present but confidence is reduced by gaps such as missing tests, partial scenario coverage, or notable divergence
   - **NOTE**: minor cleanup, artifact drift, or low-risk improvements

   Prefer evidence-based findings with file references.

8. **Make the decision**

   **Recommend archive** only when all of the following are true:
   - No CRITICAL findings remain
   - The main requirements are implemented with convincing evidence
   - Incomplete tasks are either absent or clearly stale because the code already satisfies them
   - Any remaining warnings are minor and do not undermine the change intent

   **Generate an implementation prompt** when any of the following are true:
   - One or more CRITICAL findings exist
   - A requirement or important scenario is missing or only partially implemented
   - The implementation materially diverges from the change instructions
   - The change is too ambiguous to archive confidently

9. **Output the review in a concise decision format**

   Use this structure:

   ```markdown
   ## Change Review: <change-name>

   ### Change Summary
   <2-4 sentences summarizing what the change was intended to do>

   ### Implementation Assessment
   - **Overall:** Strong | Partial | Off-track
   - **Tasks:** X/Y complete
   - **Requirements:** M/N evidenced in code
   - **Tests:** Adequate | Partial | Missing for key paths

   ### Alignment With Instructions
   - <short statement about how closely the implementation matches the proposal/specs/design/tasks>

   ### Findings
   - **CRITICAL:** <finding with file refs, if any>
   - **WARNING:** <finding with file refs, if any>
   - **NOTE:** <finding with file refs, if any>

   ### Decision
   - **Archive Recommendation:** Ready to archive
   ```

   Or, if more work is needed:

   ```markdown
   ### Decision
   - **Archive Recommendation:** Not ready

   ### Prompt For Implementing Agent
   Implement the remaining work for OpenSpec change `<change-name>`. Finish the missing requirements and update any stale task checkboxes. Focus on: (1) <gap>, (2) <gap>, (3) <gap>. Use these references: `<file>:<line>`, `<file>:<line>`. The change is ready only when the implementation matches the change artifacts and the key scenarios are covered.
   ```

**Review Heuristics**

- Be thorough in analysis, concise in output
- Bias toward concrete evidence over optimistic inference
- If something looks implemented but cannot be verified confidently, treat it as a WARNING or CRITICAL gap depending on impact
- Do not recommend archive just because most tasks are done; judge whether the actual change intent was satisfied
- Do not generate a long remediation plan; produce one concise prompt that an implementing agent can act on immediately
- If artifacts are stale but implementation is solid, say so explicitly instead of blocking archive for paperwork alone

**Graceful Degradation**

- If only tasks exist, review task completion and implementation evidence
- If tasks and specs exist, review completeness and requirement alignment
- If proposal/specs/design/tasks all exist, review intent, correctness, and coherence together
- Always note which checks were skipped because artifacts were absent

**Guardrails**

- Always end with exactly one decision path: archive recommendation or implementation prompt
- Include file references for substantive findings when possible
- Keep the final prompt concise and implementation-oriented
- Prefer `/opsx-apply` as the natural next step when more work is needed
- Prefer `/opsx-archive` as the natural next step when the change is ready
