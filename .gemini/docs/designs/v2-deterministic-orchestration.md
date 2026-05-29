# Agentic Harness: Deterministic Syntax-Injection Architecture

## 1. The Core Problem
LLMs are stochastic text generators, not state machines. When multi-agent routing logic is embedded in a monolithic prompt (e.g., the legacy `orchestrator.md`), it leads to:
*   **Instruction Drift:** The LLM forgets to enforce strict workflows (like Planning or TDD).
*   **Context Bloat:** A 5-turn conversation accumulates irrelevant historical state, confusing the LLM and wasting tokens.
*   **Non-Determinism:** The LLM attempts to fulfill tasks itself instead of routing them to the correct specialized subagent.

## 2. The Solution: Python State Machine & Syntax Injection
To enforce true operational discipline, routing logic is entirely stripped from the LLM and moved into a deterministic Python script (`prompt_classifier.py` / `orchestrator-plugin`).

**The Workflow:**
1.  **Intercept:** The `UserPromptSubmit` hook intercepts the user's raw message.
2.  **Evaluate:** Python evaluates physical artifacts on the disk (e.g., `implementation_plan.md`, test logs) and classifies the intent to determine the exact project Phase and Branch.
3.  **Inject (Syntax):** Python rewrites the user's prompt, prepending the exact CLI syntax required to trigger a subagent (e.g., `@planner`).
4.  **Execute:** The CLI natively parses the injected syntax and routes the prompt directly to the subagent, bypassing the main LLM's intuition entirely.

## 3. Hook Mechanics: Mutating the Prompt
The Python hook outputs a JSON payload utilizing two distinct fields for different purposes:

*   **`modifiedPrompt` (The Router):** This field alters the literal text the user submitted. By injecting `@subagent` syntax here, we force the CLI to natively route the task to a specialized agent. This is the engine of our deterministic routing.
*   **`system_prompt_extension` (JIT Context):** This field dynamically appends ephemeral context to the hidden system prompt for *that single turn only*. It does not pollute the permanent chat history. We use this to inject:
    *   File state summaries (so agents don't waste turns reading test logs).
    *   Just-In-Time (JIT) workflow constraints (e.g., Domain-Driven Design rules).
    *   Strict authorization warnings ("You are UNAUTHORIZED to write code").

## 4. The Great Deprecation & Phase Handoffs
The monolithic LLM persona (`orchestrator.md`) is retired. 
*   The "Orchestrator" is no longer an AI agent; it is the Python State Machine (the `orchestrator-plugin`).
*   Subagents no longer "escalate back to the orchestrator." They write their results to physical markdown artifacts on disk and halt.
*   **Manual Handoffs (HITL):** We intentionally rely on Human-In-The-Loop manual continuations between major phases. Once a subagent halts, the user acts as the "Continue" button, allowing for manual review of the artifacts before the Python hook routes to the next phase on the subsequent message.

## 5. AGENTS.md (The Roster)
With routing logic moved to Python, `AGENTS.md` transforms into a clean, standard Roster (acting as a strict README for AI assistants). It defines the available specialists in the Hub-and-Spoke model:
*   `@planner`: Architecture & Breakdown (Read-only).
*   `@implementer`: Execution & TDD (Read/Write).
*   `@reviewer`: Quality & Standards (Read-only + Shell).
*   `@adversary`: Security & QA (Read-only + Shell).

## 6. Cross-Platform Adapter Layer
Because we standardize our own agent personas across the repository, the internal Adapter Layer no longer needs to translate agent names. The Python state machine determines generic intent and invokes the standardized subagent across all platforms:
*   **Gemini CLI:** `modifiedPrompt: "@reviewer ..."`
*   **Claude Code:** `modifiedPrompt: "@reviewer ..."`
This ensures the Harness remains perfectly portable across ecosystems, utilizing a unified roster of agents while allowing the adapter to handle only minor platform-specific syntax or CLI invocation differences (if any).

## 7. Autonomous Recovery & Failure Reports
When a subagent fails a phase (e.g., the `@reviewer` rejects the `@implementer`'s code), it does not engage in an infinite conversational loop.
*   The subagent halts and writes its findings to a dynamically named artifact: `{design_doc}_failure_report.md`.
*   This specific naming convention tightly couples the failure state to the active architectural plan, allowing the Python state machine to accurately track retries and execute 3-Strike circuit breakers if necessary.

## 8. Solving Context Bloat & Data Isolation
This architecture completely eliminates the "5-turn context bloat" problem.
Because the Python hook uses `modifiedPrompt` to forcefully route tasks to specific subagents, every phase transition initiates a **fresh, isolated context window**. An `@implementer` inherits zero conversation history from the `@planner`—it only inherits the pristine `implementation_plan.md` artifact.
*   **The Artifact is the Absolute Truth:** If we start using the implementer, we assume the implementation plan is 100% ready. If a nuance was missed during planning, it should be caught during the manual HITL review phase, not preserved in an infinitely long context window. This strict context isolation mechanism absolutely requires the design document to be 100% complete; otherwise, the implementer would have to ask clarifying questions, immediately breaking the intended context isolation. This guarantees maximum token efficiency and absolute phase integrity.
