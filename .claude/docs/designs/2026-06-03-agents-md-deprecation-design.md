---
title: AGENTS.md Deprecation and Platform Consolidation
status: Proposed
date: 2026-06-03
author: harness brainstorming (Gemini + Pengbo)
topic: agents-md-deprecation
---

# AGENTS.md Deprecation and Platform Consolidation

## Part 1: Problem Understanding

The core problem: the harness spreads its instructions across too many files. The most prominent one (`AGENTS.md`) is both invisible to the model and wrong, costing maintenance without delivering anything.

Concretely:

1. `AGENTS.md` never actually loads in Claude/Gemini. The generated root file (`CLAUDE.md`) says "Please read .claude/AGENTS.md" in prose, not an `@import`. The model never sees the codegraph rules or the state machine described there.
2. It duplicates the platform file's job and drifts. It contains a tool catalog that duplicates the native MCP server's catalog, and a "Roster" of agents that no longer matches the real routing matrix. Two sources of truth guarantee rot.
3. Token space is precious. Business-level instructions will need to live in the platform root files. The harness must occupy a tiny, well-bounded footprint on the platform file — not a sprawling redirect-and-duplicate scheme.

Success looks like: one standard instruction surface per platform (`CLAUDE.md`, `GEMINI.md`, etc.) carrying a minimal, correct, idempotently-appended harness block. `AGENTS.md` is deprecated and no longer generated. The routing matrix enforcement is handled separately by a `PreToolUse` gate (handled in `2026-05-30-deterministic-routing-design.md`).

## Part 2: Technical Plan

We will deprecate `AGENTS.md` and shift to appending a minimal, idempotent instruction block directly into the platform files.

1. **Idempotent Injection (The Core Fix):**
   Update the minting engine so that instead of appending a one-line redirect ("Please read AGENTS.md..."), it idempotently injects the following block into the target platform file (e.g., `CLAUDE.md`):

   ```markdown
   <!-- harness:start -->

   **Graph-first:** Prefer the `codegraph` MCP (start with `codegraph_context`) over Grep/Glob/`find` for code search and navigation. Use text search only for non-indexed content (e.g. UI strings).

   <!-- harness:end -->
   ```

   If the markers already exist, it will replace the content between them. If not, it appends to the end of the file.

2. **Cease Minting `AGENTS.md`:**
   Remove the generation of `AGENTS.md` entirely from the minting process.

3. **Update Harness Home Anchor:**
   Update `dispatcher.py`, which currently relies on traversing upwards looking for `AGENTS.md` to locate the `harness_home` directory. We will change this anchor to a stable file that already exists in the harness directory, such as `.harness-meta.json`.

_(Note: Active deletion of existing `AGENTS.md` files is explicitly avoided to prevent unintentionally deleting a user-owned file.)_

## Part 3: Alternatives Considered

Here are the alternatives we considered and ruled out:

1. **Keep `AGENTS.md` as a "Shadow" File:**
   - **Idea:** Keep the file but explicitly `@import` it from `CLAUDE.md`.
   - **Ruled out because:** It still forces the harness to maintain a sprawling redirect-and-duplicate scheme that eats up precious token space. The harness must occupy a minimal, well-bounded footprint on the primary platform file.

2. **Include the Routing Matrix in the Platform File:**
   - **Idea:** Put the full A/B/C/D routing table into the new `<!-- harness:start -->` block inside `CLAUDE.md`.
   - **Ruled out because:** The routing matrix is already computed deterministically by the hook and will be enforced via the `PreToolUse` gate (as per the 2026-05-30 design). Making the model read the matrix as prose is advisory, redundant, wastes token space, and causes drift.

## Part 4: Detailed Implementation

Here is the exact set of changes and files we will touch to implement the deprecation and idempotent injection:

1. **`src/harness/init/minting_engine.py`**
   - **Rationale:** This is where the platform files are scaffolded.
   - **Changes:**
     - Remove the hardcoded `pointer_content` that outputs the "Please read .../AGENTS.md" prose.
     - Implement the idempotent injection logic: When generating or updating the platform file, the engine will use regex or string parsing to locate the `<!-- harness:start -->` and `<!-- harness:end -->` markers. It will replace the block if found, or append it if missing.
     - Remove the legacy branch that generates `AGENTS.md` for the Codex platform.

2. **`src/harness/runtime/dispatcher.py`**
   - **Rationale:** The dispatcher currently hard-depends on `AGENTS.md` existing as an anchor to locate the harness root directory.
   - **Changes:**
     - In `evaluate_artifacts` (around line 280), change the anchor from `AGENTS.md` to `.harness-meta.json` (which is reliably generated at the harness root).

3. **Test Suites Updates**
   - **Files touched:** `tests/e2e/test_full_harness_lifecycle.py`, `tests/e2e/test_transactional_minting.py`, `tests/integration/test_headless_generation.py`, `tests/integration/test_platform_snapshots.py`
   - **Rationale:** Test suites currently enforce the presence of `AGENTS.md`.
   - **Changes:**
     - Remove assertions requiring `AGENTS.md`.
     - Update backup/restore and structure tests to check for `.harness-meta.json` or the appended `CLAUDE.md` block instead.
