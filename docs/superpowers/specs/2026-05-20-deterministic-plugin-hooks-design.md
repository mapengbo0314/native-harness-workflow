# Deterministic Plugin Hooks Design (V4: The Portable Harness)

**Date:** 2026-05-20  
**Status:** Final Approval  
**Scope:** Transforming the auto-generated Claude Code plugin into a self-contained, portable unit that bundles the entire project harness (Agents, Skills, Rules, and Hooks) into a single installable package.

## Problem Statement

The previous design treated the plugin as a "bridge" to live files in the workspace. While this ensured live updates, it failed the "Packaging & Portability" mental model. A true Claude Code plugin should be the **container** for knowledge and logic. 

Furthermore, the initial "Harness Minting" phase (copying boilerplate) and the "Plugin Generation" phase were disconnected, creating a risk where the plugin lacked the full context of the synthesized agents (like the `@domain-sme`) and lobotomized complex skills that rely on external scripts.

Finally, there was a technical mismatch in how hooks were invoked: the generated manifest defined command hooks, but the generated source files were modules requiring package context, leading to execution failures.

## Goal

Create a **Zero-Config Portable Harness**. When a user selects "Claude Code" during `harness-wf init`, the system will:
1.  Mint the base harness.
2.  **Deep Migrate** the entire `boilerplate-agent/` and `harness/` logic into a self-contained plugin folder, preserving all scripts and templates.
3.  Include all 5 Deterministic Hooks (executable natively) to enforce the Hub-and-Spoke model.
4.  Implement active **Matrix Routing** in the hooks to bypass LLM thinking steps.
5.  Automate CodeGraph onboarding so the plugin is ready for high-performance codebase navigation immediately.

---

## The Standard Payload (From Boilerplate)

The true value of the plugin is not just the framework, but the native "Superpowers" it injects. Previous iterations failed because they did not explicitly bundle the core procedures. The V4 plugin MUST bundle the following **authoritative standard payload** sourced directly from the `boilerplate-agent/` directory:

1.  **Hub-and-Spoke Subagents:** `@orchestrator`, `@planner`, `@implementer`, `@reviewer`, `@verifier`, `@refactorer`, `@linter-agent`, `@security-auditor`, `@feature-fetcher`, `@harnesstdd`, etc.
2.  **Core Harness Skills:** All `harness-*` prefix skills (e.g., `harness-brainstorming`, `harness-test-driven-development`, `harness-subagent-driven-development`), plus essential workflows like `diagnose`, `ddd-alignment`, `prompt-engineer`, and `meta-learning`.
3.  **Governance Scripts:** Local Python evaluation scripts inside `boilerplate-agent/scripts` (e.g., `gatekeeper.py`, `extract_stacktrace.py`).

## The Self-Contained Architecture

The plugin folder (`.claude/plugin-generated/`) now owns the entire project intelligence, acting as the undisputed source of truth.

```text
.claude/plugin-generated/
├── .claude-plugin/
│   ├── plugin.json                # Tools & Hook definitions (using first-class dynamic tools)
│   └── marketplace.json           # Local installation manifest
├── src/
│   ├── hooks/                     # Executable hook scripts (e.g., prompt_interceptor.py)
│   ├── tools.py                   # Handlers for dynamically registered skill tools and Task()
│   └── dispatcher.py              # Orchestrator routing logic & Matrix classification
├── agents/                        # The FULL suite of deep-copied boilerplate subagents
│   ├── implementer.md
│   ├── planner.md
│   ├── verifier.md                # (And all others from boilerplate-agent/agents/)
│   └── domain-sme.md              # Synthesized during init
├── skills/                        # The FULL suite of deep-copied boilerplate skills
│   ├── harness-brainstorming/     # MUST include all harness-* workflows
│   ├── diagnose/
│   ├── ddd-alignment/
│   └── ...                        # (All other boilerplate skills + their scripts/templates)
└── config/                        # Project-specific context
    ├── ddd-context.json           # Live DDD invariants
    └── rules.json                 # Core mandates
```

---

## The Sequential Runtime Flow (The "Straightjacket")

By implementing these deterministic hooks, the plugin *becomes* the Harness. We effectively eliminate the need for an "outside harness" (like CLI wrappers or external babysitting scripts) during runtime. The outside harness (`harness-wf`) is relegated purely to a Build Tool used at Day 0. Once Claude Code starts, the Plugin is 100% in control.

Here is the exact sequential connection of how a task flows deterministically through this new architecture:

1.  **The Trigger (UserPromptSubmit Hook)**
    *   *Action:* User pastes a stack trace and says "Fix this".
    *   *Hook Interception:* The `UPS Hook` catches the text before the AI sees it. It identifies "Branch A: Bug Fix", compresses the stack trace to save tokens, and wraps the prompt in invisible system XML: `<matrix_route>CRITICAL DIRECTIVE: Bypass Planning. Dispatch @implementer immediately.</matrix_route>`.

2.  **The Firewall (PreToolUse Hook - Orchestrator Phase)**
    *   *Action:* The Orchestrator reads the prompt and attempts to use the `Edit` or `Bash` tool to fix the code directly.
    *   *Hook Interception:* The `PreToolUse Hook` intercepts. It checks the active persona (Orchestrator) and blocks the execution natively.
    *   *Result:* The hook returns a hard error: `[VIOLATION]: Orchestrators cannot write code. Use the Task() tool to delegate.`

3.  **The Dispatch & Auto-Injection (PreToolUse Hook - Task Interception)**
    *   *Action:* The Orchestrator complies and calls `Task("@implementer", "Fix the bug in main.py")`.
    *   *Hook Interception:* The hook reaches into the bundled payload to grab the `@implementer` markdown rules. It also *mutates* the orchestrator's prompt, appending: `[MANDATORY]: Your first action MUST be to invoke skill_harnesstdd().`
    *   *Result:* The subagent is launched, pre-loaded with its DDD context and forcibly instructed to use TDD.

4.  **The TDD & CodeGraph Enforcement (PreToolUse Hook - Subagent Phase)**
    *   *Action:* The `@implementer` attempts to use `Edit` without writing a test, or `Bash(grep)` without querying CodeGraph.
    *   *Hook Interception:* The hook checks local session state.
    *   *Result:* If a test hasn't failed first, it returns: `[TDD VIOLATION]: You must write and run a failing test before modifying production code.` If CodeGraph hasn't been used, it returns: `[EFFICIENCY VIOLATION]: Graph-First Strategy enforced. Query CodeGraph MCP before using grep.`

5.  **The Verification Guardrail (Stop Hook)**
    *   *Action:* The bug is fixed, tests pass, and the Orchestrator attempts to end the session.
    *   *Hook Interception:* The `Stop Hook` intercepts the session termination. It checks for the existence of `artifacts/verification_report.md`.
    *   *Result:* If missing, it returns: `[QA REQUIRED]: You cannot exit. Dispatch Task("@verifier") to perform robustness checks.`

6.  **Final Exit & Governance**
    *   *Action:* The `@verifier` finishes its report. The Orchestrator tries to exit again.
    *   *Hook Interception:* The `Stop Hook` runs the bundled `gatekeeper.py` script locally to perform final validation.
    *   *Result:* If `gatekeeper.py` passes, the session gracefully terminates.

---

## Advanced Guardrails & Persistence (The Logic Engine)

To resolve the "State Blindness" and "Hostage Scenario" flaws, the V4 plugin leverages proven patterns from the `harness-mem` and `claude-code-harness` ecosystems, transforming the hooks into a high-performance, deterministic execution engine.

### 1. The Continuity Runtime (State Persistence)
Instead of volatile local files, the plugin implements a project-scoped **SQLite Memory Store** (`~/.harness-mem/project.db`).
*   **Persona Tracking:** The `Task()` tool writes the `active_persona` and `parent_task_id` to the DB.
*   **Compliance Tracking:** Hooks query the DB to verify if a failing test has been recorded or if CodeGraph has been explored before allowing file modifications.
*   **Session Continuity:** A `SessionStart` hook feeds the "Continuity Briefing" (WIP tasks, last decision) into the first turn, eliminating the "blank slate" problem.

### 2. Go-Native Guardrail Engine (The Straightjacket)
Critical enforcement logic is offloaded to a **Go-native binary** (integrated via Python `subprocess` calls in hooks) to ensure sub-10ms validation latency.
*   **Hard Deny Rules:** Deterministic blocking of `sudo`, `.env` modifications, and `git push --force`.
*   **Interactive Safeguards:** Forces an `ask_user` confirmation for high-risk commands like `rm -rf` or direct pushes to `main`.
*   **5-Verb Operational Surface:** Restricts agents to a disciplined lifecycle: `/plan`, `/work`, `/review`, `/release`, `/setup`.

### 3. Escape Hatches (Anti-Stall Logic)
To prevent infinite retry loops and "hostage" terminal states:
*   **Auto-Escalation Rule:** If a hook blocks a tool call 3 consecutive times, it automatically triggers a **Recovery Flow**, injecting an `ask_user` prompt to request human intervention.
*   **PreCompact Guard:** Prevents Claude's automatic context compaction if a subagent is in a "WIP" state, ensuring the task context isn't truncated mid-flight.
*   **Human Interrupt Awareness:** The `Stop` hook is programmed to detect SIGINT (Ctrl+C) and allows an immediate exit without blocking for QA, though it marks the session as "Incomplete" in the DB.

---

## Technical Revisions for V4 Implementation

To ensure perfect integration with the harness, the following technical shifts from V3 are required:

1.  **Hook Execution Model:** 
    *   Instead of generating a generic `src/interceptor.py` that relies on package imports (`from .orchestrator_plugin...`), hooks must be generated as **executable standalone scripts** in a dedicated `src/hooks/` directory (e.g., `src/hooks/prompt_interceptor.py`).
    *   The `plugin.json` manifest must register these correctly as `command` type hooks, ensuring they can execute in isolation without PYTHONPATH issues.
2.  **Deep Copy Migration:** 
    *   `plugin_generator.py` must perform a recursive file tree copy (`shutil.copytree`) for the `skills/` and `agents/` directories, rather than just extracting markdown text. This prevents "lobotomizing" skills like `brainstorming` that rely on nested `scripts/` or HTML templates.
3.  **Active Matrix Routing (The UPS Hook):** 
    *   The `UserPromptSubmit` hook implements heuristic classification but uses **Strong Suggestions** rather than blind overrides.
    *   Example: `[ORCHESTRATOR ROUTE ADVICE]: A stack trace was detected. If the user is asking to fix this bug, dispatch @implementer. Otherwise, answer the query.`
    *   It will also perform pre-emptive token compression (e.g., calling an `extract_stacktrace` utility) before passing the prompt to the LLM.
4.  **Dynamic Skill Tools:** 
    *   Instead of a single, generic `Skill` tool, the manifest generator dynamically generates first-class tools for each skill in `plugin.json` (e.g., `skill_tdd()`, `skill_brainstorming()`). This improves LLM discoverability and auto-completion.
5.  **CodeGraph Enforcement:** 
    *   The `initialize` hook (or post-install script) verifies the presence of the `codegraph` MCP server in the host configuration, prompting installation if missing, enforcing the "Graph-First" strategy.

---

## Unified Onboarding Flow

1.  **Mint Phase:** `harness-wf init` runs. It creates the project structure, downloads skills (with all their supporting files), and generates the `@domain-sme`.
2.  **Migration Phase:** `harness/plugin_generator.py` is called. It:
    *   **Deep copies** the `agents/` and `skills/` folders into the plugin structure.
    *   Generates standalone, executable hooks in `src/hooks/`.
    *   Injects the **Full Matrix Router** logic into `src/hooks/prompt_interceptor.py`.
    *   Dynamically registers each skill as a distinct tool in `plugin.json`.
3.  **Onboarding Phase:** The user runs `setup_harness.sh`. It:
    *   Builds the CodeGraph index.
    *   Automatically runs `/plugin marketplace add` and `/plugin install`.
    *   **Result:** The user opens Claude Code and the entire harness is "just there," enforcing TDD, protecting tokens, and routing accurately without brittle workspace dependencies.

---

## Business Value: The Token Efficient Enforcer

*   **Zero-Shot Routing:** By performing heuristic classification in Python (Branch A/B/C/D), we skip the LLM's expensive "thinking" turn entirely.
*   **Trace Compression:** Native Python compression of stack traces reduces input tokens by up to 90% for bug reports.
*   **Portable Knowledge:** The plugin is the "Knowledge Package". It ensures every subagent has immediate access to DDD Context and Invariants without the LLM needing to "find" them.
*   **Engineering Rigor:** Programmatic blocking of non-TDD edits and early success claims ensures high-quality outcomes with less manual oversight.