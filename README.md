# Superpowers Agentic Harness

Welcome to the **Superpowers Agentic Harness** – a strictly orchestrated, graph-driven agentic framework designed to scale intelligence safely across the codebase. 

This repository relies on a robust **Orchestrator** mechanism equipped with pre-tool hooks, state-machine workflows (Skills), and highly specialized Subagents. By strictly bounding operations to clear **Lane Views (Routing Branches)** and enforcing a **Graph-First Strategy** for context gathering, the harness protects system integrity while executing complex engineering tasks.

---

## 🚦 Orchestration & Lane Views (Matrix Routing)

The core `OrchestratorDispatcher` categorizes incoming prompts using an LLM-assisted or fallback keyword-matching mechanism into four strict routing branches. This prevents the "generalist" context-bloat and enforces deterministic boundaries for each phase of work:

*   **Branch A: Bug Fix & Diagnosis (`@diagnose`)** 
    Focuses on stack traces, errors, and breakages. The agent is strictly **read-only** at this phase and must isolate the error using structural graph tools (`codegraph_callers`) to emit a diagnosis report before moving to resolution.
*   **Branch B: Feature Request & Architectural Planning (`@planner` → `@implementer`)** 
    Focuses on creation and implementation. Work is routed to `@planner` which operates in a read-only + web-search sandbox to draft design documents. Only upon design approval is the task handed over to the `@implementer` agent with Full FS/Git access.
*   **Branch C: Codebase Questioning & Knowledge Retrieval (`@generalist`)**
    Focuses on understanding. Agents operating in this lane are **STRICTLY UNAUTHORIZED** to mutate files and rely entirely on mapping the domain.
*   **Branch D: Surgical Edit / Fast Path (`@implementer`)**
    When minor changes (typos, color changes) are requested, the harness overrides heavy planning workflows, authorizing immediate, bounded modifications to bypass the heavy `@planner` phase.

---

## 🤖 The Subagent Roster

The framework compartmentalizes capabilities into explicitly defined, highly restrictive agents to limit blast radius and ensure quality:

*   **`@planner`**: Reads the codebase, queries the CodeGraph, searches the web, and produces design documents in `docs/designs/`. Cannot write production code.
*   **`@implementer`**: Executes TDD implementation based entirely on approved plans. Writes to `docs/progress/` and manages blockers. Does not solicit reviews directly; fails fast.
*   **`@reviewer`**: Senior evaluator agent. Assesses code against the planned designs. Strictly read-only; appends blocking feedback but does not rewrite the code.
*   **`@adversary`**: The hyper-skeptical stress-tester. Dedicated to hunting edge cases, invalidating assumptions, and enforcing resilience without flattery or hallucinations.
*   **`@diagnose`**: Runs the read-only triage phase of Branch A to systematically identify the root cause of regressions or bugs.
*   **`@generalist`**: Bound by Branch C rules (read-only) for questions or Branch D rules for fast-path surgical edits.

---

## 🧠 Our Context: The Graph-First Strategy

To prevent token exhaustion and provide massive codebase comprehension, this harness natively integrates the **CodeGraph MCP Server**. Agents are mandated to employ a tiered **Graph-First Strategy** before attempting to blindly read source files:

1.  **Level 1 (Discovery)**: `codegraph_explore` maps folder topologies; `codegraph_search` identifies exact symbol locations.
2.  **Level 2 (Understanding)**: `codegraph_context` retrieves definitions and nearby context; `codegraph_callers` traces code usage paths.
3.  **Level 3 (Impact Analysis)**: `codegraph_impact` evaluates the downstream blast radius before any structural code changes are proposed.
4.  **Level 4 (Raw Read)**: Standard `read_file` operations are treated as a last resort, strictly reserved for actively mutating logic or reading non-structural strings.

### Engineering & Domain Invariants
*   **Python-First Base**: Current services heavily emphasize Python, utilizing explicit imports, composable functions, and dataclasses.
*   **Progressive JVM Migration**: The environment is actively preparing translation bounded subsystems to Kotlin/Java.
*   **Zero UI Prototyping**: The harness strictly forbids visual/UI driven architectural brainstorming in favor of text/code-centric designs.

---

## ⚡ Superpower Skills

The harness uses a rigorous State Machine of "Skills" to inject workflow discipline before an agent is allowed to act.

Whenever an intent is received, the agent **MUST** invoke relevant skills (found in `.gemini/skills/`). Some key workflows include:
*   **`using-harness-superpowers`**: The master gatekeeper. Enforces the priority of skills over default prompts. 
*   **`harness-brainstorming-plans`**: Bypasses UI prototyping, forces text-based architectural alignment.
*   **`harness-test-driven-development` / `tdd`**: Red-Green-Refactor enforcement.
*   **`verification-before-completion`**: The mandatory final check before an agent can conclude a task.

---

## 🛡️ Hooks & System Protections

The orchestrator sits atop robust system-level hooks that intercept agent actions prior to execution, providing a deterministic layer of security:

*   **Pre-Tool Use Sandbox (`pre_tool_use.py`)**: 
    Intercepts any tool execution request and evaluates it for catastrophic actions.
    *   **Anti-Destruction**: Regex heuristics block dangerous bash commands like `rm -rf /` or wildcard recursive deletions before they hit the shell.
    *   **Secret Protection**: Explicitly blocks file tools or bash commands from touching `.env` files (except safe `.env.sample` templates) to prevent credentials from entering the LLM context or logs.
*   **Langfuse Telemetry**: Native, deeply integrated observation traces (`@observe`). Intent classification, phase calculation, and model selection are tracked via environment injection to ensure full auditability of agent performance.