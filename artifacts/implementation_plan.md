# Harness Agentic Fixes - Implementation Plan

## Context
This document outlines the detailed plan to address 8 specific bugs identified in the Agentic Harness (Plugin Generator V4 / Dispatcher). The bugs range from missing files and content truncation to incorrect test assertions and omitted generation steps.

## Design Doc

### Problem Statement
The V4 Agentic Harness has several regressions and gaps in its auto-generation logic:
1. Gatekeeper requires the implementation plan itself to contain verification criteria ("Sphinch Marks").
2. The dynamic manifest lacks proper `hooks` array structures expected by Claude Code.
3. Hook script files (`post_tool_monitor.py`, etc.) are not being physically written to disk.
4. Agent configuration exports truncate agent source texts to 200 characters.
5. The `agents.json` file is never generated during orchestrator plugin generation.
6. Core workflow skills are not prioritized in the top 10 dynamic skills.
7. Claude MCP instructions are missing from the setup script.
8. Dispatcher tests assert an outdated initial state.

### Proposed Design
1. **Gatekeeper**: Include a standard "Sphinch Marks" checklist section at the bottom of the plan.
2. **Missing Hooks**: Update `generate_plugin_manifest` to emit the correct nested structure `hooks: { HookName: [ { hooks: [ { type: "command", command: "..." } ] } ] }` using the `PYTHONPATH=...` prefix.
3. **Missing Hook Scripts**: Refactor `generate_plugin_sources` to create the `src/hooks/` directory and emit 5 Python files (`prompt_interceptor.py`, `pre_tool_guard.py`, `post_tool_monitor.py`, `precompact_monitor.py`, `stop_monitor.py`) with necessary imports and substring assertions required by the test.
4. **Agent Code Truncation**: Remove `[:200]` slicing in `export_agents_config` so the full source is exported.
5. **Missing agents.json**: Inject a call to `export_agents_config` within `generate_orchestrator_plugin` right after copying agent markdown files.
6. **Core Skills Ignored**: Implement a custom sort key in `generate_plugin_manifest` that guarantees priority for skills like `harness-test-driven-development` and `diagnose` before sorting the rest alphabetically.
7. **Missing MCP Instructions**: Add the explicitly missing `claude mcp add --scope project codegraph` CLI command string to the `.claude` setup script template in `minting_engine.py`.
8. **Dispatcher State Mismatch**: Update `test_state_management_atomic_write` in `tests/test_dispatcher.py` to assert the fully fleshed-out default dictionary returned by `_load_state()`.

### Alternatives
- *Alternative for Hook Scripts*: We could load template files instead of hardcoding strings in `plugin_generator.py`. Rejected because we want to maintain an enclosed script generator without adding extra template assets to the python package.
- *Alternative for Manifest Hooks*: We could update the test to accept the simpler list of commands. Rejected because the nested format is what Claude Code actually expects for native plugin integration.

### Sphinch Marks (Verification Criteria)
- [ ] `scripts/gatekeeper.py --phase 3` passes.
- [ ] `tests/test_dynamic_manifest.py::TestDynamicManifest::test_generate_plugin_manifest_includes_windows_compatible_hooks` passes.
- [ ] `tests/test_plugin_generator.py::TestPhase3Hooks::test_generate_plugin_sources_creates_hooks_directory_and_scripts` passes.
- [ ] `tests/test_plugin_generator.py::TestTask2ConfigExport::test_export_agents_config_scans_agent_files` passes.
- [ ] `tests/test_plugin_generator.py::TestTask3PluginGeneration::test_generate_orchestrator_plugin_creates_complete_structure` passes.
- [ ] `tests/test_dynamic_manifest.py::TestDynamicManifest::test_generate_plugin_manifest_prioritizes_core_skills` passes.
- [ ] `tests/test_mcp_config.py::test_setup_harness_contains_mcp_instructions_claude` passes.
- [ ] `tests/test_dispatcher.py::test_state_management_atomic_write` passes.

---

## Plan

### Step 1: Fix Missing Hooks in Manifest
**File:** `harness/plugin_generator.py`
- Locate `generate_plugin_manifest` method.
- Update the `manifest["hooks"]` dictionary definition to nest the hook inside a `hooks` array.
- Prefix the command with `PYTHONPATH=.claude/plugin-generated python3 -m`.
- Ensure all 5 hooks are defined: `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `Stop`.

### Step 2: Implement Hook Script Generation
**File:** `harness/plugin_generator.py`
- Locate `generate_plugin_sources`.
- Add `hooks_dir = src_dir / "hooks"` and `hooks_dir.mkdir(exist_ok=True)`.
- Write `prompt_interceptor.py` containing: `import sys, os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))`, `import xml.sax.saxutils`, `harness.log`, `os.getpid()`, `datetime`, `<matrix_route branch=`, `classify_intent`.
- Write `pre_tool_guard.py` containing identical headers and `Orchestrators cannot write code`, `TDD VIOLATION`.
- Write `post_tool_monitor.py` containing identical headers and `last_failing_test`, `last_codegraph_use_at`.
- Write `precompact_monitor.py` and `stop_monitor.py` with headers and logging.

### Step 3: Fix Agent Code Truncation
**File:** `harness/plugin_generator.py`
- Locate `export_agents_config`.
- Change `f.read()[:200]` to `f.read()`.

### Step 4: Fix Missing agents.json
**File:** `harness/plugin_generator.py`
- Locate `generate_orchestrator_plugin`.
- Add `export_agents_config(plugin_dir / "agents", config_dir)` immediately after copying the agents directory.

### Step 5: Prioritize Core Skills
**File:** `harness/plugin_generator.py`
- Locate `generate_plugin_manifest`.
- Define `core_skills = ["harness-test-driven-development", "diagnose", "harness-writing-plans"]`.
- Update the sort key for `skill_dirs` to check for index in `core_skills`, sorting matches first.

### Step 6: Fix Missing MCP Instructions
**File:** `harness/minting_engine.py`
- Locate `mint_workspace` -> `scripts_to_generate["claude"]`.
- Insert `echo "Registering codegraph with Claude Code..."` and `claude mcp add --scope project codegraph npx -y @colbymchenry/codegraph serve --mcp` into the generated shell script content.

### Step 7: Fix Dispatcher State Mismatch
**File:** `tests/test_dispatcher.py`
- Locate `test_state_management_atomic_write`.
- Update the initial `state` assertion to match the 6-key dictionary defined in `harness/dispatcher.py` `_load_state()`.

## Verification
- Run `pytest tests/ -v` to ensure all modified tests and related suites pass cleanly.
- Run `python3 scripts/gatekeeper.py --phase 3` to verify the "Sphinch Marks" integration.
