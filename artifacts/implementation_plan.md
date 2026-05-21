# Plugin Generator V4 Implementation Plan

## Overview
Rewrite `harness/plugin_generator.py` to match the V4 Deterministic Plugin Hooks Design. This plan breaks the rewrite down into 4 test-driven phases.

## Task 1: Phase 1 - Deep Copy Migration (DONE)
**Context:** The previous `plugin_generator.py` performed shallow text extraction of `.md` files. We must now deep copy the `boilerplate-agent/agents` and `boilerplate-agent/skills` directories to preserve all scripts and templates.
**Steps:**
1. Write/update tests in `tests/test_plugin_generator.py` to assert that subdirectories inside `skills/` (like `scripts/`) are successfully copied to the `.claude/plugin-generated/skills/` directory.
2. Modify `harness/plugin_generator.py` to replace the markdown extraction logic with `shutil.copytree` for both the `agents` and `skills` directories.
3. Ensure the test passes.

## Task 2: Phase 2 - Core Logic Engine (Dispatcher & State) (DONE)
**Context:** Implement the "Native Python Enforcement" and "Atomic State" logic.
**Steps:**
1. Update `generate_plugin_sources()` to generate a much smarter `src/dispatcher.py` that includes the atomic JSON state manager (using `os.mkdir` locks and `os.replace`).
2. Implement Matrix Routing logic (parsing Branches A/B/C/D) inside the generated code.
3. Implement 5-Verb operational guardrails inside the generated code.
4. Add tests to verify the content of the generated `dispatcher.py` meets the new requirements.

## Task 3: Phase 3 - Standalone Hooks Execution (DONE)
**Context:** Generate isolated hook scripts with cross-platform compatibility.
**Steps:**
1. Update the generator to create a new `src/hooks/` directory.
2. Generate `prompt_interceptor.py` (UPS), `pre_tool_guard.py` (Firewall/TDD), and `stop_monitor.py` (Verification guardrail).
3. Inject the Python import resolution headers (`sys.path.insert`) and XML sanitization logic into the generated scripts.
4. Ensure executable bits/shebangs are properly handled (or cross-platform Python `-m` invocation is prepared for Phase 4).

## Task 4: Phase 4 - Dynamic Manifest & Tiered Tools
**Context:** Update `plugin.json` generation.
**Steps:**
1. Modify `generate_plugin_manifest()` to dynamically scan the copied `skills/` folder.
2. Register the "Top 10" skills as first-class tools (e.g., `skill_harnesstdd`), and register the remainder behind a wrapper.
3. Register the Windows-compatible hook commands (e.g., `["python", "-m", "src.hooks.prompt_interceptor"]`).
4. Validate the generated manifest structure in tests.