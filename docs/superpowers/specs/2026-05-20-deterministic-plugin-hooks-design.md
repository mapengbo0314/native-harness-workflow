# Deterministic Plugin Hooks Design (V2: Context-Aware Lazy Loading)

**Date:** 2026-05-20  
**Status:** Approved  
**Scope:** Enhancing the auto-generated Claude Code plugin to enforce deterministic harness behaviors via `PreToolUse` and `UserPromptSubmit` hooks, while optimizing token usage and developer experience.

## Problem Statement

The embedded harness currently relies on LLM compliance to follow instructions defined in `AGENTS.md` and `orchestrator.md`. While the generated Claude Code plugin successfully exposes the `Skill` and `Task` tools, it lacks active enforcement.

An initial V1 design proposed using `SessionStart` to inject massive context payloads and hard-rewriting user prompts on error detection. This was rejected due to:
1.  **Token Bloat**: Injecting the entire DDD dictionary and routing matrix on every session start wastes tokens for simple queries.
2.  **Stale State**: Compiling live `.md` files into static `.json` files inside the plugin causes desynchronization when developers update the live workspace files.
3.  **Loss of Agency**: Hard-rewriting prompts destroys user intent (e.g., asking a question about a stack trace vs. asking the AI to fix it).

## Goal

Create a "Perfect Harness" that mirrors the power of the Matt Pocock Superpowers plugin. The plugin will act as a silent, intelligent gateway that **lazy-loads** context only when needed, reads **live workspace files**, and uses **soft-enforcement** to guide the Orchestrator without hijacking the developer's intent.

---

## Architecture Updates (The "Lazy Load" Model)

### 1. Live File Reading (No More Stale JSON)
We will delete the logic that copies `orchestrator.md` and `CONTEXT.md` into static JSON files. 
Instead, the plugin's `dispatcher.py` and tools will read directly from the live workspace paths (e.g., `.claude/orchestrator.md`, `docs/domain/CONTEXT.md`). If the developer updates a ubiquitous term, the plugin uses it on the very next turn.

### 2. The `PreToolUse` Hook (Lazy Context Injection)
Instead of a `SessionStart` hook that bloats the context window immediately, we will intercept the exact moment the Orchestrator tries to do complex work: when it invokes the `Task` tool.

**Trigger:** `PreToolUse` (Matcher: `Task`)
**Logic:**
1.  When Claude Code attempts to dispatch a subagent (e.g., `@planner` or `@implementer`), the hook intercepts the call.
2.  The hook reads the live `docs/domain/CONTEXT.md`.
3.  It bundles the DDD Context, the strict invariants, and the requested Subagent's persona into the tool's execution context.
**Benefit:** Claude Code remains incredibly fast and token-light for general chat. It only pays the "Context Tax" when it actually transitions into a specialized subagent to write code.

### 3. The `UserPromptSubmit` Hook (Intelligent Error Routing)
We will leverage the existing `boilerplate-agent/scripts/extract_stacktrace.py` logic natively within the plugin.

**Trigger:** `UserPromptSubmit`
**Logic (`src/hooks/prompt_interceptor.py`):**
1.  Receives the raw user prompt.
2.  Scans the text for error signatures (`Traceback`, `Panic:`, etc.) using the logic from `extract_stacktrace.py`.
3.  **Soft Enforcement:** If an error is detected, it does *not* rewrite the user's prompt. Instead, it securely appends a `[System Note]` to the end of the prompt block:
    > *"[System Note: A stack trace was detected in your input. If the user is reporting a bug, you MUST invoke `Skill("systematic-debugging")` before responding. If they are just asking an architectural question, answer normally.]"*
4.  **UX Transparency:** Prints to the user's terminal: `[Harness] Auto-detected stack trace. Appended systematic-debugging guidance.`

**Benefit:** Retains developer agency while actively prompting the AI to use the Superpowers skills when things break.

---

## The Superpowers Synergy

This architecture makes our plugin function identically to the Matt Pocock `superpowers` plugin, but customized for our Hub-and-Spoke model:
1.  **Tool Exposure:** Just like the official plugin exposes `/skills`, our plugin exposes `Skill()` and `Task()`.
2.  **Workflow Enforcement:** It forces the AI to use the `systematic-debugging` skill upon detecting errors.
3.  **Native Integration:** It doesn't rely on the LLM "remembering" to use bash commands to read files; the Python plugin handles the file I/O safely and cleanly.

---

## Implementation Steps

1.  **Refactor Config Export:** Remove the `export_orchestrator_config` JSON conversion from `harness/plugin_generator.py`.
2.  **Update Dispatcher:** Rewrite `src/dispatcher.py` to parse the live `.claude/AGENTS.md` and `.claude/orchestrator.md` files dynamically.
3.  **Build Hooks:** 
    *   Create `src/hooks/prompt_interceptor.py` and port the `extract_stacktrace.py` logic into it.
    *   Register the `UserPromptSubmit` hook in the `plugin.json` manifest.
4.  **Update Task Tool:** Modify `src/tools.py:invoke_task` to read `docs/domain/CONTEXT.md` and bundle it with the subagent dispatch.