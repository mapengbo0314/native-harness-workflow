# Adhoc Remediation Plan: Finalizing V4 Plugin Hooks

**Date:** 2026-05-20
**Context:** Following the implementation of the V4 Plugin Generator scaffolding, multiple independent code reviews (including adversarial subagents and external reviews) identified critical gaps. While the packaging architecture (Deep Copy, Manifest, Hook Scripts) is sound, the *logic engine* inside the generated hooks remains stubbed, and several edge cases violate the deterministic "Straightjacket" model.

This document serves as the definitive punch list to finalize the V4 architecture.

---

## 1. The Stubbed Guardrails (Hook Logic Engine)

The generated hooks currently log activity but fail to enforce the Hub-and-Spoke mandates. We must update the string templates in `harness/plugin_generator.py` to output actual enforcement logic.

### 1.1 True Matrix Routing (`prompt_interceptor.py`)
*   **Current State:** Sanitizes XML but blindly wraps all input in Branch A (Bug Fix).
*   **Fix Required:** 
    *   The generated script must import the `dispatcher` and call `classify_intent(user_input)`.
    *   It must dynamically emit distinct `<matrix_route>` XML directives based on the result (Branch A, B, C, or D) as defined in the V4 spec.

### 1.2 The TDD & Orchestrator Firewall (`pre_tool_guard.py`)
*   **Current State:** Hardcoded `is_rejected = False`.
*   **Fix Required:**
    *   **Orchestrator Firewall:** If the active persona (from `.harness_state.json`) is "orchestrator" and the tool is `Bash` or `Edit`, immediately reject with: `[VIOLATION]: Orchestrators cannot write code. Use the Task() tool.`
    *   **TDD Enforcement:** If the active persona is "implementer" and the tool is `Edit`, the hook must verify in `.harness_state.json` that a failing test was previously executed. If not, reject.
    *   **CodeGraph Enforcement:** Reject `Bash(grep)` or massive `Read` calls if `codegraph_search` hasn't been utilized recently.

### 1.3 The 3-Strike Escape Hatch (`pre_tool_guard.py`)
*   **Current State:** Escalation block is present but unreachable due to `is_rejected = False`.
*   **Fix Required:** Wire the rejection logic from 1.2 into the existing rejection counter. Ensure that upon the 3rd consecutive rejection, the hook safely aborts or modifies the prompt to force human intervention (`ask_user`).

### 1.4 Verification Gatekeeper (`stop_monitor.py`)
*   **Current State:** Stubbed comment. Does not run `gatekeeper.py`.
*   **Fix Required:** 
    *   Implement `subprocess.run(["python", "../scripts/gatekeeper.py", "--phase", "3"])`.
    *   If the exit code is non-zero, the hook must `sys.exit(1)` to hard-block session termination.
    *   **Human Interrupt:** Handle `KeyboardInterrupt` / SIGINT gracefully so a human can force-quit without triggering the verification block.

---

## 2. Portability & Truncation Flaws

The core routing mechanism (`dispatcher.py`) suffers from fatal context truncation and pathing issues.

### 2.1 The 200-Character Agent Lobotomy (`dispatcher.py`)
*   **Current State:** The migration fallback logic truncates agent files during load: `agent_file.read_text()[:200]`. This means subagents only receive the first 200 chars of their system prompt.
*   **Fix Required:** Remove the `[:200]` slice in `_load_agents_config()`. The dispatcher must load and inject the full agent markdown.

### 2.2 Local Skill Resolution (`orchestrator_plugin.py`)
*   **Current State:** The `read_skill()` method hardcodes paths pointing *outside* the plugin (e.g., `../../../../.claude/skills`).
*   **Fix Required:** Update `read_skill()` to resolve paths strictly within the plugin's own bundled `skills/` directory (`os.path.join(os.path.dirname(__file__), '../skills')`). This ensures true portability.

---

## 3. The UX Bottleneck & Stale Workspace

The onboarding experience for Claude Code users requires manual intervention.

### 3.1 Claude Code `/plugin install` UX (`minting_engine.py`)
*   **Current State:** `setup_harness.sh` uses `echo` to print Claude Code slash commands, forcing the user to manually copy-paste them into the chat interface.
*   **Fix Required:** 
    *   Add highly visible `[ACTION REQUIRED]` terminal blocks in the script emphasizing the manual steps.
    *   Investigate if pre-committing `.claude/settings.json` (which holds active plugin state) bypasses the need for manual slash commands on a fresh clone.

### 3.2 Python Version Guard (`minting_engine.py`)
*   **Current State:** `setup_harness.sh` does not verify the runtime environment.
*   **Fix Required:** Add a `python3 --version` check to the generated `setup_harness.sh` script, aborting if the version is < 3.8.

### 3.3 Regenerate the Live Workspace
*   **Current State:** The `.claude/plugin-generated/` folder committed to the repo is stale and lacks the `src/hooks` and deep-copied directories from our recent code changes.
*   **Fix Required:** Once items 1 and 2 are coded, run the `harness-wf init` script locally to generate the finalized V4 plugin architecture, and commit the fresh `.claude/plugin-generated/` folder to source control.

---
**Status:** Pending Implementation.