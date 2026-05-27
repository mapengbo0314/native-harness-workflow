# Deterministic Orchestration Implementation Plan

## Part 1: Problem Understanding

**The Problem:**
When building complex, multi-agent AI systems within a CLI environment, relying on a Large Language Model (LLM) to act as the "Manager" or "Orchestrator" is fundamentally unreliable. We currently dump all routing logic, constraints, and workflows into a massive system prompt (`orchestrator.md`). Because LLMs are text predictors and not rigid state machines, they inevitably fail in three major ways:
1. **Instruction Drift:** They "forget" to enforce critical workflows (like Test-Driven Development or Planning) when a user gives an urgent or conflicting command.
2. **Context Bloat:** After a few conversational turns, the LLM's memory is overwhelmed by history, which drastically increases token costs and degrades reasoning quality.
3. **Loss of Discipline:** Instead of delegating tasks to the correct specialized subagents (like the Planner or Implementer), the orchestrator LLM tries to be "helpful" and write the code or solve the problem directly, breaking the Hub-and-Spoke architecture.

**The Business Need:**
We need to remove the routing and decision-making burden from the LLM. We must replace it with strict, deterministic Python code that forces the CLI to route tasks to isolated specialists, ensuring 100% adherence to our workflows, cutting token costs, and preventing hallucinations.

---

## Part 2: Technical Plan

**The Architecture:**
We will replace the massive LLM orchestrator persona with a Python-based state machine (`orchestrator-plugin`) that intercepts user messages. It consists of three main components:

1. **The Interceptor (Hook):** We will use the `UserPromptSubmit` hook. When a user types a message, this Python script runs *before* the main LLM processes it. It evaluates physical files on the disk (e.g., checking if `implementation_plan.md` or `{design_doc}_failure_report.md` exists) to definitively prove what Phase of the project we are in.
2. **The Router (Syntax Injector):** Based on the proven Phase and the user's intent, the script will rewrite the user's prompt by prepending specific CLI syntax (like `@planner` or `@implementer`) using the `modifiedPrompt` JSON field. This forcefully triggers the CLI to bypass the main LLM and launch a specialized subagent. This guarantees that subagents start with a 100% fresh context window, completely eliminating historical context bloat. We will also use `system_prompt_extension` to inject Just-In-Time (JIT) rules (like Domain-Driven Design constraints) only when needed.
3. **The Adapter Layer (Platform Mechanics):** We will maintain a standardized roster of agents (e.g., `@reviewer`) across all platforms (Gemini, Claude, Codex, etc.). The adapter layer will purely handle the underlying semantics of the specific platform's hook definition and invocation mechanisms, ensuring our Python logic interfaces correctly without needing to translate agent names.

**The Cleanup:**
We will completely retire the old monolithic `orchestrator.md` file. We will also rewrite `AGENTS.md` to be a strict, clean Roster that defines our standardized specialists (`@planner`, `@implementer`, `@reviewer`, `@adversary`) and their tool boundaries. Finally, we will establish that handoffs between major phases (like Planning -> Implementing) require a manual Human-In-The-Loop (HITL) continuation, ensuring the user can review the generated artifacts before the Python hook routes to the next phase.

---

## Part 3: Alternatives Considered

1. **Pure Prompt-Based Orchestration:** We originally used a massive LLM persona (`orchestrator.md`) to handle routing logic. This was ruled out because LLMs struggle with strict adherence over long sessions, leading to instruction drift, context bloat, and a failure to enforce the Hub-and-Spoke isolation properly.
2. **Using `system_prompt_extension` for Routing:** We considered injecting rules into the hidden system prompt to tell the main LLM to route tasks. This was ruled out because it still relies on the LLM's intuition to follow those rules and make the actual routing decision. By mutating the `modifiedPrompt` instead, we force the CLI platform to handle the routing natively, ensuring 100% determinism.
3. **Automated Subagent Handoffs:** We considered letting subagents automatically trigger the next phase (e.g., the Implementer automatically passing code to the Reviewer). This was ruled out in favor of Human-In-The-Loop (HITL) manual continuations. Forcing the user to act as the "Continue" button provides a vital safety checkpoint, allowing humans to review generated artifacts (like the plan) before spending tokens on the next phase.
4. **JSON-Based State Tracking (`state.json`):** We discussed implementing a formal JSON state tracker file to manage the workflow phases. This was ruled out as over-engineering for this iteration. Relying on physical markdown artifacts (like `implementation_plan.md` or `{design_doc}_failure_report.md`) is simpler, more visible to the user, and robust enough for our needs.

---

## Part 4: Detailed Implementation

Here is the detailed list of files we will change or create to implement this architecture:

1. **`src/harness/runtime/dispatcher.py` (The State Machine Engine)**
   *   **Change:** Refactor the dispatcher to evaluate physical artifacts on disk (e.g., `implementation_plan.md`, `*_failure_report.md`) to deterministically calculate the current Phase.
   *   **Change:** Ensure the dispatcher outputs a standardized generic intent dictionary (e.g., `{ "target_agent": "@planner" }`) for the adapter layer to consume. The exact matrix logic for mapping intents will be handled separately.

2. **`src/harness/hooks/prompt_classifier.py` (The Hook Entrypoint)**
   *   **Change:** Wire the script to pass the intercepted user input to `dispatcher.py` for phase/intent evaluation, and then to the active platform adapter to generate the final hook payload.

3. **`src/harness/adapters/` (The Adapter Layer)**
   *   **Change:** Define a `BaseAdapter.format_hook_response(routing_decision, context_extension)` interface.
   *   **Change:** Implement this interface across all platform adapters (e.g., `gemini.py`, `claude.py`, `codex.py`). Each adapter will map the generic intent to the specific JSON payload/syntax required by its CLI platform (using `modifiedPrompt` for routing syntax and `systemPromptExtension` for JIT context).

4. **`src/harness/runtime/context_builder.py` (The JIT Context Injector)**
   *   **Change:** Implement a `build_context(phase)` function.
   *   **Change:** Construct the ephemeral rule strings based on the Phase (e.g., appending DDD rules during Planning, or TDD guidelines during Implementation). This string is passed to the adapter to become the `system_prompt_extension`.

5. **`src/harness/templates/boilerplate/AGENTS.md` AND `.gemini/AGENTS.md` (The Roster)**
   *   **Change:** Completely overwrite the contents of both files. Remove all LLM pseudo-code and routing instructions.
   *   **Change:** Add the exact roster definitions for `@planner`, `@implementer`, `@reviewer`, and `@adversary`, explicitly detailing their descriptions, strict mandates, and toolset boundaries (e.g., "Reviewer: Read-only + Shell").

6. **`src/harness/templates/boilerplate/orchestrator.md` AND `.gemini/orchestrator.md`**
   *   **Change:** Delete these files entirely to formalize the deprecation of the LLM persona.

7. **Subagent Templates (`src/harness/templates/boilerplate/agents/*.md`)**
   *   **Change `planner.md`:** Remove any instruction to "escalate to the orchestrator". Add mandate: "You MUST write your final design to `artifacts/implementation_plan.md` and then halt."
   *   **Change `implementer.md`:** Remove escalation clauses. Add mandate: "If execution fails fundamentally, write findings to `artifacts/{design_doc}_failure_report.md` and halt."
   *   **Change `reviewer.md`:** Remove auto-fix instructions. Add mandate: "If the code fails review, write findings to `artifacts/{design_doc}_failure_report.md`."

8. **Config Files (`agent.json`, `pyproject.toml`, `onboarding/tools.json` inside boilerplate)**
   *   **Change:** Remove references to `orchestrator.md` as an LLM entrypoint, ensuring the system recognizes `orchestrator-plugin` purely as the Python-driven routing logic.
