# Deterministic Plugin Hooks Design

**Date:** 2026-05-20  
**Status:** Draft  
**Scope:** Enhancing the auto-generated Claude Code plugin to enforce deterministic harness behaviors via `SessionStart` and `UserPromptSubmit` hooks.

## Problem Statement

The embedded harness currently relies on LLM compliance to follow instructions defined in `AGENTS.md` and `orchestrator.md`. While the recently generated Claude Code plugin successfully exposes the `Skill` and `Task` tools and intercepts agent dispatches, there are still vulnerabilities:

1.  **The "Competency Illusion"**: When Claude Code starts, it hasn't necessarily read the DDD `CONTEXT.md` or internalized the `orchestrator.md` rules before answering the first prompt. It *acts* ready, but isn't grounded.
2.  **Hallucinated Routing**: When a user pastes a stack trace, Claude might try to fix the bug itself instead of strictly following "Branch A" (routing to `@implementer` with the `systematic-debugging` skill).

## Goal

Transform the `orchestrator-plugin` from a passive tool provider into an **active enforcer**. By leveraging Claude Code's native plugin hooks, we will write deterministic Python logic that automatically injects the necessary context on startup and rigidly intercepts and rewrites user prompts to force the LLM down the correct architectural paths.

---

## Architecture Updates

The plugin generator (`harness/plugin_generator.py`) will be updated to output additional hook files and register them in the `plugin.json` manifest.

### 1. Configuration Data Flow

The generated plugin currently bundles:
-   `config/orchestrator.json`: Contains the full text of `orchestrator.md`.
-   `config/agents.json`: Contains the roster and instructions for all subagents.
-   `config/ddd-context.json`: Contains the ubiquitous language and strict invariants.
-   `config/rules.json`: Contains the core mandates.

The new hooks will read these static JSON files natively via Python, completely bypassing the need for the LLM to use the `Read` tool to learn about its environment.

### 2. The `SessionStart` Hook (Context Injection)

**Trigger:** Fires automatically when Claude Code is launched in the directory.

**Logic (`src/hooks/session_start.py`):**
1.  Reads `config/ddd-context.json`.
2.  Reads `config/orchestrator.json`.
3.  Reads `config/agents.json` to get the list of available subagents.
4.  Constructs a massive "System Override" payload.
5.  **Output:** Returns a modified system prompt (or an initial synthetic user message) that explicitly commands Claude: 
    > *"SYSTEM OVERRIDE: You are the Orchestrator. Here is your DDD context: [...]. Your available subagents are: [...]. You must use the `Task` tool to delegate."*
6.  **UX:** Prints a console message using ANSI formatting to let the user know the harness is locked and loaded.

**Benefit:** Eliminates the "Competency Illusion". The AI is 100% grounded in the project's specific domain and routing rules before the user even types a single letter.

### 3. The `UserPromptSubmit` Hook (Deterministic Routing)

**Trigger:** Fires every time the user presses Enter, intercepting the raw text before it reaches the LLM.

**Logic (`src/hooks/prompt_interceptor.py`):**
1.  Receives the raw user prompt.
2.  **Detection Rule 1: Stack Traces & Errors**
    *   Uses Regex to look for common error signatures (`Traceback`, `Error:`, `Exception:`, `Panic:`).
    *   If detected, it deterministically enforces **Branch A (Bug Fix / Diagnosis)** from the `orchestrator.md` matrix.
    *   It silently appends a directive to the prompt:
        > *"[PLUGIN ENFORCEMENT]: A stack trace was detected. DO NOT GUESS. You MUST immediately invoke `Skill(name="systematic-debugging")` and then use `Task(agent_name="implementer", prompt="...")` to resolve this."*
3.  **Detection Rule 2: Ambiguous Architecture Requests**
    *   If the user asks "How should we build X?"
    *   It appends a directive enforcing **Branch B**:
        > *"[PLUGIN ENFORCEMENT]: This is an architectural request. You MUST invoke `Task(agent_name="planner", ...)` before writing any code."*

**Benefit:** Hardcodes the orchestrator's decision matrix. The LLM can no longer "forget" to use systematic debugging when it sees an error.

---

## Implementation Steps

### Phase 1: Update Plugin Manifest
Modify `generate_plugin_manifest` in `harness/plugin_generator.py` to add the new hooks to the `plugin.json` schema:

```json
"hooks": {
  "SessionStart": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/src/hooks/session_start.py\""
        }
      ]
    }
  ],
  "UserPromptSubmit": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/src/hooks/prompt_interceptor.py\""
        }
      ]
    }
  ],
  "PreToolUse": [ ... existing interceptor ... ]
}
```

### Phase 2: Create the Hook Scripts
Update `generate_plugin_sources` to write out the new Python hook files inside a `src/hooks/` directory.

-   **`src/hooks/session_start.py`**: Needs to parse the JSON configs and output the system prompt modification payload expected by Claude Code.
-   **`src/hooks/prompt_interceptor.py`**: Needs to implement the regex logic and output the rewritten prompt string.

### Phase 3: Test and Integrate
1.  Regenerate the plugin locally.
2.  Launch Claude Code to verify the `SessionStart` hook injects the context properly.
3.  Paste a mock stack trace to verify the `UserPromptSubmit` hook rewrites the prompt and forces the `Skill` and `Task` tool invocations.

---

## Future Extensibility
Because we control the generation of the Python logic, we can easily add more deterministic rules later:
*   **PreToolUse (Edit)**: Block file edits if `pytest` wasn't run recently (enforcing strict TDD).
*   **PostToolUse (Task)**: Automatically run `benchmark_gate.py` to verify the subagent didn't break invariants.