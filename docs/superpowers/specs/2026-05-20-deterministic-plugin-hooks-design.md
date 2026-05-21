# Deterministic Plugin Hooks Design (V4: The Portable Harness)

**Date:** 2026-05-20  
**Status:** MVP Ready (Strict Determinism)  
**Scope:** Transforming the auto-generated Claude Code plugin into a self-contained, portable unit that bundles the entire project harness (Agents, Skills, Rules, and Hooks) into a single installable package.

## Problem Statement

The previous design treated the plugin as a "bridge" to live files in the workspace. While this ensured live updates, it failed the "Packaging & Portability" mental model. A true Claude Code plugin should be the **container** for knowledge and logic. 

Furthermore, the initial "Harness Minting" phase (copying boilerplate) and the "Plugin Generation" phase were disconnected, creating a risk where the plugin lacked the full context of the synthesized agents (like the `@domain-sme`) and lobotomized complex skills that rely on external scripts.

## Goal

Create a **Zero-Config Portable Harness**. When a user selects "Claude Code" during `harness-wf init`, the system will:
1.  Mint the base harness.
2.  **Deep Migrate** the entire `boilerplate-agent/` and `harness/` logic into a self-contained plugin folder, preserving all scripts and templates.
3.  Include all 5 Deterministic Hooks (executable natively) to enforce the Hub-and-Spoke model.
4.  Implement active **Matrix Routing (Branches A/B/C/D)** in the hooks to strictly bypass LLM thinking steps.
5.  Automate CodeGraph onboarding so the plugin is guaranteed to have high-performance codebase navigation immediately.

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
│   ├── plugin.json                # Tools & Hook definitions (using tiered dynamic tools)
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

1.  **The Trigger & Matrix Routing (UserPromptSubmit Hook)**
    *   *Action:* User submits a prompt or stack trace.
    *   *Hook Interception:* The `UPS Hook` catches the text before the AI sees it. It compresses stack traces to save tokens, and classifies the intent into one of four rigid branches. It wraps the prompt in an invisible XML **CRITICAL DIRECTIVE** to force compliance.
    *   **The 4 Branches (Strict Enforcement):**
        *   **Branch A: Bug Fix** (e.g., Stack trace pasted). -> `<matrix_route>CRITICAL DIRECTIVE: Bypass Planning. Dispatch @implementer immediately with diagnose skill.</matrix_route>`
        *   **Branch B: Feature Request** -> `<matrix_route>CRITICAL DIRECTIVE: Dispatch @planner to write a spec using harness-brainstorming.</matrix_route>`
        *   **Branch C: Question/Retrieval** -> `<matrix_route>CRITICAL DIRECTIVE: Answer directly using CodeGraph context. Do not mutate files.</matrix_route>`
        *   **Branch D: Surgical Edit** -> `<matrix_route>CRITICAL DIRECTIVE: Dispatch @implementer directly without planning.</matrix_route>`

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
    *   *Result (TDD):* If a test hasn't failed first, it returns: `[TDD VIOLATION]: You must write and run a failing test before modifying production code.`
    *   *Result (CodeGraph):* If CodeGraph hasn't been used, it returns: `[EFFICIENCY VIOLATION]: Graph-First Strategy strictly enforced. Query CodeGraph MCP before using grep.` *(Note: CodeGraph indexing is guaranteed by the minting phase, so strict enforcement is safe).*

5.  **Context Preservation (The PreCompact Guard)**
    *   *Action:* A subagent loop runs long, triggering Claude Code's native context compaction.
    *   *Hook Interception:* A token-monitoring hook detects threshold proximity.
    *   *Result:* Automatically injects a "Persona Reminder" block into the context stream to prevent the AI from "forgetting" its strict role constraints (Anti-Amnesia) during long iterations.

6.  **The Verification Guardrail (Stop Hook)**
    *   *Action:* The bug is fixed, tests pass, and the Orchestrator attempts to end the session.
    *   *Hook Interception:* The `Stop Hook` intercepts the session termination. It checks for the existence of `artifacts/verification_report.md`.
    *   *Result:* If missing, it returns: `[QA REQUIRED]: You cannot exit. Dispatch Task("@verifier") to perform robustness checks.`

7.  **Final Exit & Governance**
    *   *Action:* The `@verifier` finishes its report. The Orchestrator tries to exit again.
    *   *Hook Interception:* The `Stop Hook` runs the bundled `gatekeeper.py` script locally to perform final validation.
    *   *Result:* If `gatekeeper.py` passes, the session gracefully terminates.

---

## Native Python Guardrails & Local Persistence

To resolve "State Blindness" and "Hostage Scenarios" while maintaining a strictly "Zero-Config" and highly portable architecture, the plugin leverages a **Native Python + Local JSON** enforcement model.

### 1. The Local JSON State Store (Per-Developer Isolation)
State is tracked via a simple, git-ignored JSON file located at `.claude/plugin-generated/config/.harness_state.json`.
*   **Persona Tracking:** The `Task()` tool writes the `active_persona` to this local JSON file. Hooks read this file to know who is executing tools.
*   **Compliance Verification:** When the AI runs a test, the hook updates the JSON state. When the AI attempts to use `Edit`, the hook checks the JSON state to ensure a failing test was recently recorded.
*   **Branch Isolation:** Because the file lives inside the project workspace (and is git-ignored), there is zero risk of state leaking across different Git branches or between different engineers working on the same repository.

### 2. Native Python Guardrail Engine (Zero-Latency Enforcement)
Critical enforcement logic is implemented directly within the generated Python hook scripts.
*   **Standard Library Only:** To ensure absolute portability, all `src/hooks/` scripts MUST use only the Python Standard Library (`json`, `sys`, `os`, `re`, `subprocess`). No external dependencies are permitted.
*   **Hard Deny Rules:** Python natively inspects `Bash` tool payloads, blocking `sudo`, `.env` modifications, and `git push --force`.
*   **Tiered Tool Registration (Context Optimization):** Instead of registering 50+ individual tools which bloats the context window, the plugin registers only the Top 10 Core Skills (e.g., `skill_harnesstdd`, `skill_brainstorming`) as first-class dynamic tools. The long-tail of niche skills is accessed via a single `invoke_skill(name)` wrapper tool.

### 3. Escape Hatches (Anti-Stall Logic)
To prevent infinite retry loops and "hostage" terminal states:
*   **Auto-Escalation Rule:** The local JSON tracks hook rejections. If a hook blocks a tool 3 consecutive times, the Python script triggers a **Recovery Flow**, mutating the prompt to force the AI to `ask_user` for help.
*   **Human Interrupt Awareness:** The `Stop` hook is designed to recognize human interruptions (SIGINT). If a user forces an exit, the hook bypasses QA guardrails but marks the local JSON session as "Incomplete."

---

## MVP Scope & Deferred Features

To maintain implementation speed and focus on core value, the following features are explicitly **DEFERRED** to post-MVP versions:

1.  **State Security:** MVP will not attempt to block the AI from manually using Bash to edit `.harness_state.json`. We assume a "cooperative agent" model for the prototype.
2.  **Auto-Sync:** Updates to source skills/agents in the project root will require manual re-generation of the plugin via `harness-wf init` to update the plugin folder.
3.  **Multi-User Sync:** State remains strictly local/git-ignored. Centralized state sync is out of scope.

---

## Implementation Safeguards (The "Gotchas")

To ensure the "Straightjacket" doesn't fail at the OS, API, or concurrency levels, the following implementation details MUST be enforced:

1.  **Windows Portability & Invocation:** 
    *   Do NOT rely on POSIX execution bits (`chmod`) for Windows compatibility.
    *   The `plugin.json` manifest MUST explicitly invoke the interpreter (e.g., `["python", "-m", "src.hooks.prompt_interceptor"]`) using a cross-platform reference.
    *   Use `pathlib` for all file manipulations to handle `/` vs `\` path separators.
2.  **Atomic State Management (Race Condition Prevention):**
    *   Claude Code supports parallel tool execution. To prevent corruption of `.harness_state.json`, hooks MUST use atomic writes: Write to `.harness_state.tmp.json` then use `os.replace()` for an atomic swap.
    *   Use `os.mkdir(".harness_state.json.lock")` as a cross-platform atomic mutex for sensitive write operations.
3.  **Standalone Import Resolution:**
    *   Since hooks are generated in `src/hooks/`, the generator MUST inject a path-resolution header into every script to ensure they can import from `src/dispatcher.py`:
        `import sys, os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))`
4.  **XML Sanitization & Injection Prevention:**
    *   User input within the `UPS Hook` MUST be sanitized to prevent "Prompt Injection" via closing tags (e.g., `</matrix_route>`). Use XML-safe escaping or CDATA blocks for the wrapped user prompt.
5.  **Plugin Observability (Logging):** 
    *   Hooks MUST append to `.claude/plugin-generated/config/harness.log`. Every entry MUST include a timestamp and `os.getpid()`.
6.  **Minimal Runtime Requirements:**
    *   `setup_harness.sh` MUST verify a minimum Python version (Python 3.8+).
7.  **Co-Location Risk (Self-Sabotage):**
    *   *Security Warning:* Since hooks and state reside in the same workspace as the agent's write-access, strict security is not possible. For the MVP, we assume a "cooperative agent" model.

---

## Technical Revisions for V4 Implementation

1.  **Hook Execution Model:** Hooks are generated as standalone scripts using only `stdlib` Python, with explicit interpreter invocation in the manifest.
2.  **Deep Copy Migration:** `plugin_generator.py` performs a recursive file tree copy (`shutil.copytree`) for `skills/` and `agents/`.
3.  **Strict Matrix Routing (The UPS Hook):** Implements heuristic classification using **CRITICAL DIRECTIVES** for Branches A/B/C/D. Uses sanitized XML wrapping.
4.  **CodeGraph Enforcement:** Enforces a strict "Graph-First" requirement, as CodeGraph is guaranteed by the minting phase.
5.  **Token Efficiency & Amnesia Guard:** Implements Tiered Tool Registration to prevent context bloat, and a PreCompact token monitor.
6.  **Atomic Persistence:** Implements the `os.replace` atomic-swap pattern for `.harness_state.json`.

---

## Unified Onboarding Flow

1.  **Mint Phase:** `harness-wf init` runs. It creates the project structure, downloads skills, configures CodeGraph, and generates the `@domain-sme`.
2.  **Migration Phase:** `harness/plugin_generator.py` is called. It:
    *   **Deep copies** the `agents/` and `skills/` folders.
    *   Generates standalone, executable hooks in `src/hooks/`.
    *   Injects the **Strict Matrix Router** logic into `src/hooks/prompt_interceptor.py`.
3.  **Onboarding Phase:** The user runs `setup_harness.sh`. It:
    *   Builds the CodeGraph index and installs the plugin.
    *   **Result:** The harness is ready, strictly enforcing TDD, routing accurately, and protecting the token window.