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
    *   User input must be XML-escaped or safely wrapped in CDATA before insertion into the route envelope so prompts cannot close or spoof `<matrix_route>` tags.

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
    *   First check for `artifacts/verification_report.md`. If missing, reject with: `[QA REQUIRED]: You cannot exit. Dispatch Task("@verifier") to perform robustness checks.`
    *   Implement `subprocess.run(["python", "../scripts/gatekeeper.py", "--phase", "3"])`.
    *   If the exit code is non-zero, the hook must `sys.exit(1)` to hard-block session termination.
    *   **Human Interrupt:** Handle `KeyboardInterrupt` / SIGINT gracefully so a human can force-quit without triggering the verification block.

### 1.5 Task Interception & Forced Skill Injection (`pre_tool_guard.py` / `tools.py`)
*   **Current State:** Task dispatch records `active_persona`, but it does not enforce the V4 dispatch contract. Subagents are not guaranteed to receive DDD context, full bundled persona instructions, or mandatory first-step skill usage.
*   **Fix Required:**
    *   When the orchestrator invokes `Task`, load the target agent markdown from the plugin's bundled `agents/` directory.
    *   Append DDD context from `config/ddd-context.json` to the dispatched prompt.
    *   If the target agent is `implementer`, inject: `[MANDATORY]: Your first action MUST be to invoke skill_harnesstdd().`
    *   Preserve Matrix branch information in `.harness_state.json` so downstream hooks can enforce branch-specific rules.

### 1.6 State Write-Side Tracking (`post_tool_monitor.py`)
*   **Current State:** The plan checks for "failing test was previously executed" and "CodeGraph was used recently", but there is no deterministic mechanism to record those facts. `PreToolUse` can only inspect intent; it cannot prove a command actually failed or capture tool output.
*   **Fix Required:**
    *   Generate `src/hooks/post_tool_monitor.py` and register it in `plugin.json` as a `PostToolUse` hook.
    *   On completed `Bash` test commands, record the command, exit code, timestamp, and whether it was a failing test in `.harness_state.json`.
    *   On completed CodeGraph MCP/tool usage, record `last_codegraph_use_at` and the tool name.
    *   On `Edit` by `implementer`, require a recent failing test marker before allowing production-code edits.
    *   On `Bash(grep)` or large `Read`, require recent CodeGraph usage before allowing the tool.
    *   Treat `PreToolUse` as the enforcement point and `PostToolUse` as the evidence-recording point.

### 1.7 Hard-Deny Safety Rules (`pre_tool_guard.py`)
*   **Current State:** V4 requires native hard-deny safety checks, but the current remediation list does not name them.
*   **Fix Required:**
    *   Reject `Bash` payloads containing `sudo`.
    *   Reject attempts to edit or overwrite `.env` files.
    *   Reject `git push --force` and equivalent force-push forms.
    *   Route all hard-deny rejections through the same consecutive-rejection counter and 3-strike recovery flow.

### 1.8 PreCompact Anti-Amnesia Guard (`precompact_monitor.py`)
*   **Current State:** The V4 design calls for 5 deterministic hooks, including a context-preservation hook, but only three generated hook scripts are represented in this plan.
*   **Fix Required:**
    *   Generate `src/hooks/precompact_monitor.py`.
    *   Register the hook in `plugin.json` using the same interpreter-based, cross-platform command style as the other hooks.
    *   Inject a compact persona reminder containing `active_persona`, Matrix branch, DDD invariants, and current TDD/verification status before compaction.
    *   Log all PreCompact activity to `config/harness.log`.

### 1.9 Shared Hook Infrastructure (`plugin_generator.py`)
*   **Current State:** New hook scripts are being added piecemeal, which risks inconsistent imports, logging, and state writes.
*   **Fix Required:**
    *   Inject the standalone import-resolution header into every generated hook script: `import sys, os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))`.
    *   All hook state writes must go through the atomic state helper: write `.harness_state.tmp.json`, then `os.replace()` it over `.harness_state.json`.
    *   Guard sensitive state writes with a directory mutex created via `os.mkdir(".harness_state.json.lock")` so parallel Claude Code tool execution cannot corrupt state.
    *   Every hook must append timestamped, PID-tagged entries to `config/harness.log`.
    *   Hook scripts must stay standard-library-only.

---

## 2. Portability & Truncation Flaws

The core routing mechanism (`dispatcher.py`) suffers from fatal context truncation and pathing issues.

### 2.1 The 200-Character Agent Lobotomy (`dispatcher.py`)
*   **Current State:** The migration fallback logic truncates agent files during load: `agent_file.read_text()[:200]`. This means subagents only receive the first 200 chars of their system prompt.
*   **Fix Required:** Remove the `[:200]` slice in `_load_agents_config()`. The dispatcher must load and inject the full agent markdown.

### 2.2 Local Skill Resolution (`orchestrator_plugin.py`)
*   **Current State:** The `read_skill()` method hardcodes paths pointing *outside* the plugin (e.g., `../../../../.claude/skills`).
*   **Fix Required:** Update `read_skill()` to resolve paths strictly within the plugin's own bundled `skills/` directory (`os.path.join(os.path.dirname(__file__), '../skills')`). This ensures true portability.

### 2.3 Stale `agents.json` Overrides Deep-Copied Agents (`plugin_generator.py`)
*   **Current State:** `dispatcher.py` only falls back to the deep-copied `agents/` directory when `config/agents.json` is missing. A stale or truncated `agents.json` can therefore override the full bundled agent markdown.
*   **Fix Required:**
    *   Regenerate `config/agents.json` from the final plugin `agents/` directory after deep copy and domain-agent synthesis.
    *   Ensure exported agent `source` values contain the full markdown, not truncated previews.
    *   Consider deleting stale generated config before regeneration so removed/renamed agents cannot linger.

### 2.4 Core Skill Prioritization for Tiered Tools (`plugin_generator.py`)
*   **Current State:** First-class skill tools are selected alphabetically from the skills directory. This can omit V4-critical workflows depending on directory names.
*   **Fix Required:**
    *   Register mandatory core tools first: TDD, brainstorming/planning, diagnosis/systematic debugging, DDD alignment, review/verification, and dispatching workflows.
    *   Fill any remaining Top-10 slots deterministically after the mandatory set.
    *   Keep the generic `invoke_skill(name)` wrapper for all long-tail bundled skills.

---

## 3. The UX Bottleneck & Stale Workspace

The onboarding experience for Claude Code users requires manual intervention.

### 3.0 End-to-End `harness-wf init` Contract (`minting_engine.py` / `plugin_generator.py`)
*   **Current State:** The generated harness pieces exist, but the onboarding contract is not explicit enough to prove the repo is ready for Claude Code after `harness-wf init`.
*   **Fix Required:**
    *   `harness-wf init` must perform the full Day 0 build in order: mint base harness, synthesize/patch domain agents, deep-copy agents/skills/scripts into `.claude/plugin-generated/`, export DDD/rules/agent config, generate all hooks, generate `plugin.json`, and write setup scripts.
    *   The generated `.claude/plugin-generated/` directory must be self-contained: no runtime dependency on `boilerplate-agent/`, root `.claude/skills`, or local source-tree paths outside the plugin.
    *   `CLAUDE.md` must clearly point users to `.claude/AGENTS.md`, `.claude/orchestrator.md`, and the generated setup script.
    *   The final CLI output must distinguish what was automated from what still requires manual Claude Code slash commands.
    *   `harness-wf init` should print a concise "ready checklist" with the exact next command: `sh .claude/scripts/setup_harness.sh`.

### 3.1 Claude Code `/plugin install` UX (`minting_engine.py`)
*   **Current State:** `setup_harness.sh` uses `echo` to print Claude Code slash commands, forcing the user to manually copy-paste them into the chat interface.
*   **Fix Required:** 
    *   Prefer a best-effort automatic install path if the local `claude` binary exposes a documented or discoverable non-interactive plugin command.
    *   Feature-detect plugin CLI support at runtime instead of hardcoding assumptions. If unsupported, fall back to explicit manual slash commands.
    *   Do not mutate `.claude/settings.json` as the primary install mechanism unless the file format and plugin activation semantics are confirmed stable; treat settings pre-seeding as an investigated optimization, not the default path.
    *   Add highly visible `[ACTION REQUIRED]` terminal blocks in the script emphasizing the manual steps.
    *   Investigate if pre-committing `.claude/settings.json` (which holds active plugin state) bypasses the need for manual slash commands on a fresh clone.
    *   Print the exact expected slash commands in order:
        *   `/plugin marketplace add .claude/plugin-generated --scope project`
        *   `/plugin install orchestrator-plugin@local-orchestrator-marketplace --scope project`
    *   After manual installation, instruct the user to restart or reload Claude Code if required for hooks/tools to become active.

### 3.2 Python Version Guard (`minting_engine.py`)
*   **Current State:** `setup_harness.sh` does not verify the runtime environment.
*   **Fix Required:** Add a `python3 --version` check to the generated `setup_harness.sh` script, aborting if the version is < 3.8.

### 3.3 CodeGraph Setup Must Be Guaranteed (`minting_engine.py`)
*   **Current State:** Claude setup runs CodeGraph indexing with `|| true`, so failures are ignored even though strict runtime enforcement assumes CodeGraph is available.
*   **Fix Required:**
    *   Make CodeGraph indexing fail loudly for Claude Code plugin setup, or clearly mark the plugin as not ready until indexing succeeds.
    *   Verify the CodeGraph MCP registration command succeeds, or print an `[ACTION REQUIRED]` block with the exact manual remediation.
    *   Do not enable strict CodeGraph tool-use enforcement unless setup has recorded CodeGraph readiness in `.harness_state.json` or equivalent config.

### 3.4 Runtime Readiness Marker (`setup_harness.sh`)
*   **Current State:** There is no single machine-readable marker that tells hooks whether Day 0 setup completed successfully.
*   **Fix Required:**
    *   After Python, plugin payload, and CodeGraph checks pass, write a local readiness state into `.claude/plugin-generated/config/.harness_state.json`.
    *   Include at minimum: `setup_complete`, `python_version`, `codegraph_ready`, `plugin_install_manual_steps_printed`, and `strict_enforcement_enabled`.
    *   Hooks must fail softly with an `[ACTION REQUIRED]` setup message when readiness is missing, instead of trapping the user in strict enforcement before onboarding is complete.
    *   The readiness file remains git-ignored/local and must be created with the same atomic state helper used by hooks.

### 3.5 First-Run Smoke Test (`setup_harness.sh`)
*   **Current State:** The setup script does not prove the generated plugin can import its dispatcher, read bundled skills, or locate bundled scripts before the user enters Claude Code.
*   **Fix Required:**
    *   Run a lightweight Python smoke check that imports `src.dispatcher`, loads `config/ddd-context.json`, verifies bundled `agents/`, `skills/`, and `scripts/gatekeeper.py` exist, and confirms every hook script is present.
    *   If the smoke check fails, print `[ACTION REQUIRED]` with the failing path/check and do not mark strict enforcement as ready.

### 3.6 Regenerate the Live Workspace
*   **Current State:** The `.claude/plugin-generated/` folder committed to the repo is stale and lacks the `src/hooks` and deep-copied directories from our recent code changes.
*   **Fix Required:** Once items 1 and 2 are coded, run the `harness-wf init` script locally to generate the finalized V4 plugin architecture, and commit the fresh `.claude/plugin-generated/` folder to source control.

---
**Status:** Pending Implementation.
