# Document State Auto-Sync & Failure Tracking Design

**Date:** 2026-05-26
**State:** Proposed

## Part 1: Business Problem
The system currently tracks design documents across a four-stage lifecycle (`proposed`, `inprogress`, `completed`, `reference`). However, when an implementation fails during the `inprogress` phase, agents are instructed to write a standalone `_failure_report.md` file directly into the `docs/reference/` directory.

This creates an architectural conflict: the `reference/` directory is strictly meant for archiving historical, completed documents. Placing active failure blockers in an archival folder fragments the context of an ongoing task. It makes it difficult for agents and users to track why a feature currently marked as `inprogress` is blocked, as the failure data is disconnected from the main progress tracker (`inprogress/{design_name}-progress.md`). We need to unify failure reporting with the existing active tracking mechanisms to maintain a single source of truth for in-progress work.

Furthermore, making agents manually move files between `proposed/`, `inprogress/`, etc., is redundant and error-prone if `manifest.json` is the actual source of truth.

## Part 2: Technical Plan
We will shift to a **Manifest-Driven Auto-Sync Architecture**. Agents will no longer be responsible for manually moving design documents between folders (`proposed/`, `inprogress/`, `completed/`, `reference/`). 

1. **Agent Responsibility**: Agents will only edit `docs/manifest.json` to change a document's state. 
2. **System Responsibility**: We will implement a git hook (e.g., `PreCommit`) that watches for changes to `manifest.json`. When a state change is detected, a Python script will automatically `git mv` the design document to the correct directory matching its new state before the commit finalizes.
3. **Progress Docs & Failures**: The progress document (`{design_name}-progress.md`) will be created directly in `docs/inprogress/`. Any failure reports will be appended directly into this progress document under a "Current Blockers" section, eliminating the need for standalone failure report files. When the design moves to `completed` in the manifest, the system will automatically move the design doc to `completed/` and the progress doc to `reference/`.

This reduces agent overhead, prevents desynchronization between the folder structure and the manifest, and keeps failure tracking neatly organized within the active progress doc.

## Part 3: Alternatives Considered
1. **Agent-Driven Shell Commands (The Legacy Way):** We initially considered forcing the agents to run `git mv` commands to keep the folder structure synchronized with their updates to `manifest.json`. We ruled this out because LLMs frequently forget to execute mechanical, multi-step shell commands, leading to desynchronization between the JSON state and the physical file tree.
2. **Standalone Failure Reports:** We considered writing separate `{design}_failure_report.md` files in the `docs/reference/` folder when a task failed. We ruled this out because `reference/` is meant for archived client material or completed docs, and separating active blockers from the main progress tracker creates disjointed context for the Implementer agent.
3. **No Folders, Just Manifest:** We considered keeping all documents in a single flat directory and relying entirely on `manifest.json` for state. We ruled this out because physical subdirectories (`proposed/`, `inprogress/`, `completed/`) make it vastly easier for humans to browse the repository and understand project status at a glance without having to parse JSON.

## Part 4: Detailed Implementation
We will build a single-source-of-truth syncing mechanism and simplify the agent templates.

1. **`src/harness/templates/boilerplate/scripts/sync_manifest_state.py` (NEW):**
   - *Rationale:* A Python script that reads `docs/manifest.json`. It checks the `state` of every document and compares it to its physical location. If a document labeled `inprogress` is still sitting in `docs/proposed/`, the script executes a `git mv docs/proposed/{name}.md docs/inprogress/{name}.md` (and similarly for `completed/` transitions). This centralizes the movement logic.

2. **`src/harness/templates/boilerplate/hooks/hooks.json`:**
   - *Rationale:* We will add a `PreCommit` trigger (or update an existing one) to execute `sync_manifest_state.py` automatically. This guarantees that before any agent successfully commits work, the file system is perfectly synchronized with the manifest.

3. **`src/harness/templates/boilerplate/agents/implementer.md`, `planner.md`, `reviewer.md`, `verifier.md` (and active `.gemini/agents/` copies):**
   - *Rationale:* We will strip out all instructions telling the agents to physically move design documents. We will instruct them to *only* update `manifest.json`. For the Implementer and Reviewer, we will update the failure mandate to state: "Append failure findings, stack traces, and required fixes to the 'Current Blockers' section of `docs/inprogress/{design_name}-progress.md`."

4. **`src/harness/templates/boilerplate/docs/README.md` (and active `.gemini/docs/README.md` if present):**
   - *Rationale:* Update the system documentation to reflect that agents must not move files manually, and explain how the auto-sync hook operates.