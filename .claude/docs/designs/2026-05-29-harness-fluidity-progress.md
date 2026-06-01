---
title: Progress — Harness Fluidity (Single-Source Adapters & Mint-Verify)
status: In Progress
design: .claude/docs/designs/2026-05-29-harness-fluidity-design.md
branch: feat/harness-fluidity-adapters
started: 2026-05-30
---

# Progress: Harness Fluidity — Single-Source Adapters & Mint-Verify

Executing via subagent-driven development. Routing (the former Slice 3) is a separate
design and NOT in scope here.

## Slice 1 — Mint-and-verify safety net (build against CURRENT code)

- [x] S1-T1: `tests/e2e/_mint_helpers.py` — `mint_platform(tmp_path, platform) -> Path` headless mint fixture ✅ commit `b5b6a0f`, 5 tests pass. VERIFIED roots: claude→`.claude/plugin-generated/`, gemini→`.gemini/`. Helper drives full CLI with mocking; `subprocess.run` mocked (so S1-T4 must assert written MCP config, not the CLI call).
- [x] S1-T6: `tests/sandbox/runner.py` — ✅ commit `029eaac`, 7 pass. `run_scenario(plugin_root, scenario) -> RoutingResult(branch,skill,agent)`; instantiates `OrchestratorDispatcher(plugin_root/"config")` + `classify_intent`. CLI path unchanged. VERIFIED against a real minted plugin_root. NOTE for S1-T5: patch `harness.runtime.dispatcher.query_llm=None` for deterministic keyword routing.
- [x] S1-T2: `tests/integration/test_adapter_drift_guard.py` — ✅ commit `379bdb3`, 14 tests pass. No drift found (3 representations already identical). Throwaway, retire in S2-T7.
- [x] S1-T3: matrix L1+L2 — ✅ commit `e0fba44`, 28 pass + 1 xfail(strict). Gemini verified distinct: `agent.json`/`skills.json`, events `PreCompress`/`AfterTool`, no `plugin-generated/`/`agents.json`/`plugin.json`. No "for ." bug in current code. **BUG-1 (tracked):** claude `agents.json` paths are ABSOLUTE → not portable; xfail(strict) auto-promotes when fixed (candidate fix in S2-T4 manifest gen).
- [x] S1-T4: matrix `test_skills_and_mcp_installed` — ✅ commit `b70d95e`, 32 pass. 16 boilerplate skills cross-checked present. MCP via Approach 2 (assert `configure_cli` command tokens `mcp add codegraph @colbymchenry/codegraph` — no `.mcp.json` written, "mcp.json generation removed in task 2"). No bugs.
- [x] S1-T5: matrix `test_routing_scenarios` — ✅ commit `0d68142`, 32 pass + 3 xfail. Only 1 scenario declares `expected_behavior` (thin L5 — worth adding more later). **BUG-2 (tracked → routing design D7):** "rename…everywhere" expects D but keyword classifier → B (D keywords miss rename/refactor); xfail(strict). NOT fixed here (routing is the separate design).
- [x] S1-T7: `tests/e2e/test_mint_static_validity.py` — ✅ commit `f405473`, 16 pass. JSON parses, 16 SKILL.md + 6 agent frontmatter valid, 5 hooks compile, 8 src files zero-harness, hygiene clean. **BUG-3 FIXED (real source fix in cli.py):** `_validate_claude_plugin` `exec_module` was compiling hooks → shipped cpython-311 .pyc; now swept. Verified independently: fresh mint ships 0 pyc.
- [x] S1-T8: `tests/e2e/test_hook_execution_contract.py` — ✅ commit `1d7d05d`, 43 pass/3 skip. 4 hooks × 2 platforms run via declared interpreter (prompt_classifier via real `uv run`); pre_tool_use allow(0)/deny(2) pair. Found platform contract diff: claude deny=exit2, gemini deny=`{"decision":"deny"}` JSON. No bugs. ~140s (uv+mint) — acceptable for e2e.

**✅ SLICE 1 COMPLETE** — mint-and-verify safety net in place (L1→L5). Net caught BUG-1 (xfail), BUG-2 (xfail→routing design), BUG-3 (FIXED). Slice 2 refactor must keep this net green.

## Slice 2 — One platform abstraction: JSON profile + polymorphic builder

- [x] S2-T1: `platform_profiles.json` + `tests/unit/test_platform_profiles.py` — ✅ commit `701df88`, 55 pass. claude+gemini accurate (+ codex/cursor/generic stubs). Captures gemini tool_mappings asymmetry faithfully. `plugin_dir_name: "harness-wf-plugin"` declared as data (no minting change yet). Verified values match live adapters.
- [x] S2-T2: `src/harness/adapters/profile.py` + `tests/unit/test_profile.py` — ✅ commit `7fb760c`, 41 pass. Frozen `PlatformProfile` + accessors (`skill_invocation`/`subagent_invocation`/`subagent_text_call`). Stdlib-only VERIFIED (loads standalone w/o harness pkg; raises `ProfileError` on unknown). Accessors match live adapters exactly.
- [x] S2-T3: `src/harness/adapters/base.py` — ✅ commit `3e592be`, net stayed green (88 pass/3 xfail). `RuntimeAdapter(ABC)` (9 runtime methods + identity) + `PlatformBuilder(ABC)` (6 mint methods incl. new `assemble_layout`); `PlatformAdapter(RuntimeAdapter, PlatformBuilder)` composes both, `assemble_layout` delegates to `generate_core_infrastructure` (backward-compat, zero behavior change).
- [x] S2-T4: ✅ commit `8db960f`, drift-guard 14/14, net green, +25 test_builders. Both adapters' 8 syntax methods now read from profile; `assemble_layout` is canonical (dispatches on `supports_plugin`), `generate_core_infrastructure` shims to it. Folder still `plugin-generated` (rename deferred to S2-T4b).
- [x] S2-T4b: `harness-wf-plugin` rename — ✅ commits `32796b5` (rename, 17 files) + `d6f9374` (circular-import fix). Fresh claude mint → `.claude/harness-wf-plugin/` VERIFIED. Name sourced from `profile.plugin_dir_name`. Full `tests/` suite: **494 passed, 3 pre-existing failures, 0 errors**. **REGRESSION caught+fixed by controller (subagent missed it):** the rename added a top-level profile import to plugin_generator.py → circular import (only surfaced via minting_engine-first import order, e.g. test_autonomous_recovery_loop); fixed with lazy call-time import. Committed `.claude/plugin-generated/` repo dir left intact (user regenerates on re-mint); 2 hook tests still point at it (expected).
- [x] S2-T5: `adapters/__init__.py` — ✅ commit `42b7528`, +24 tests, drift-guard green. `_REGISTRY` dict replaces if/elif; `get_builder`/`get_runtime_adapter`/`get_adapter` all use it; unknown→`GenericAdapter` (contract preserved, 40 callers checked).
- [x] S2-T6: `minting_engine.copy_runtime_modules` — ✅ commit `aae5e32`. Ships runtime slice by copy (`runtime_adapter.py`, `profile.py`, `platform_profiles.json`); dynamically emits no-arg `get_adapter()` shim (`platform_adapter.py`). Includes packaging fix in `pyproject.toml`.
- [x] S2-T7: DELETE legacy code — ✅ commit `a649fbb`. Deleted the old monolith (`platform_adapter.py`), the 5 standalone adapters (`platform_adapter_*.py`), and the S1-T2 drift-guard test.
- [x] S2-T8: Update tests — ✅ commit `aae5e32`/`a649fbb`. Repointed `tests/unit/test_platform_adapters.py` to the new canonical runtime slice. Resolved API rate-limiting issues in E2E tests by mocking `query_llm`.

**✅ SLICE 2 COMPLETE** — One platform abstraction achieved. Test suite is green (`pytest tests/`).

## Current Blockers / Tracked Defects

- None blocking.
- **BUG-1** (caught by S1-T3): claude `agents.json` agent paths are absolute, not relative to plugin root → breaks portability. Documented via xfail(strict). Fix candidate during S2-T4 (manifest generation) or as a standalone fix.
- **BUG-2** (caught by S1-T5): keyword classifier routes "rename/refactor everywhere" to B not D (D keyword list misses rename/refactor). xfail(strict). Belongs to the Deterministic Routing design (D7) — fix there, not in fluidity.

## Log

- 2026-05-30: Branch `feat/harness-fluidity-adapters` created. Progress doc initialized.
