# Langfuse Instrumentation Refactor Design

**Date:** 2026-05-27  
**Status:** Approved  
**Scope:** Centralize Langfuse initialization and session-level tracing across hook, dispatcher, and LLM client

---

## Part 1: Problem Understanding

**The Business Problem:**

You have a distributed harness system that routes user prompts through an orchestrator to different specialized agents (implementer, planner, reviewer, etc.). Every interaction flows through hooks that invoke LLM calls (Gemini, Claude, OpenAI) to make routing decisions and generate responses.

Currently, Langfuse observability is **scattered across three locations** with **no unified lifecycle**:
1. The hook entry point (`prompt_classifier.py`) initializes trace IDs but only calls flush once
2. The dispatcher (`dispatcher.py`) has raw `@observe` decorators with generic names
3. The LLM client (`llm_client.py`) has raw `@observe(as_type="generation")` but no explicit naming

**The pain points:**
- Traces in Langfuse UI are hard to read (no semantic span names like "dispatch_to_implementer")
- Session IDs aren't consistently propagated (Claude/Gemini session IDs aren't used)
- Langfuse initialization logic is duplicated across files
- Flush behavior is implicit and hard to trace

**The goal:** Consolidate Langfuse setup into one instrumentation module that:
- Initializes traces once with Claude/Gemini session correlation
- Provides explicit, meaningful span names automatically
- Guarantees cleanup (flush) at operation boundaries
- Removes duplication and makes the system maintainable

---

## Part 2: Technical Plan

**High-Level Architecture:**

We'll create `langfuse_instrumentation.py` that manages a **persistent session trace**. Every prompt in a Claude Code session becomes a child span in one unified trace.

**How it fits together:**

1. **Session Trace (Automatic):**
   - Claude Code provides `CLAUDE_SESSION_ID` in the environment for every hook execution
   - We use this directly as the Langfuse session ID
   - Langfuse automatically groups all traces with the same session ID together
   - The session trace stays "open" in Langfuse (it's just a grouping concept, not something we manage)

2. **Per-Prompt Spans:**
   - Each prompt from the user creates a **child span** within that session
   - `init_langfuse_prompt_span(prompt_text)` opens a new span for that prompt
   - The dispatcher and LLM client operations become **grandchild spans** under the prompt span

3. **Lifecycle:**
   - `init_langfuse_trace(project_root)` — Called at hook start. Sets up session from `CLAUDE_SESSION_ID`, creates a prompt span
   - `ensure_flush()` — Called at hook end. Flushes the current prompt span
   - Next prompt = new child span in the same session (no state management needed)

4. **Clean & Stateless:**
   - No files created or persisted
   - Langfuse naturally groups all prompts by session ID
   - Simple, zero-overhead approach

**What changes:**

- ✅ **Create new:** `langfuse_instrumentation.py` (session + prompt span management)
- ✅ **Update:** `prompt_classifier.py` (call init/flush with prompt context)
- ✅ **Update:** `llm_client.py` and `dispatcher.py` (add explicit span names)
- ❌ **No state files or persistence logic**

---

## Part 3: Alternatives Considered

**Alternative 1: Per-Prompt Traces (Original Approach)**
- **What:** Each prompt gets its own isolated trace in Langfuse
- **Why we ruled it out:** You specifically wanted to see the entire session at a glance, not jump between separate traces. Per-prompt traces lose the context of the user's workflow across multiple interactions.

**Alternative 2: State File Persistence**
- **What:** Store the session trace ID in `.claude/plugin-generated/state/langfuse_session.json` to ensure consistent IDs across hook invocations
- **Why we ruled it out:** No state persistence requested. Plus, the environment variable `CLAUDE_SESSION_ID` is already available at runtime, so we don't need to manage it ourselves.

**Alternative 3: Async Flushing**
- **What:** Don't call `ensure_flush()` in the hook; let Langfuse batch uploads asynchronously
- **Why we ruled it out:** Hooks need deterministic behavior. If the hook exits before traces are uploaded, we might lose data. Explicit flush guarantees everything lands in Langfuse before moving on.

**Alternative 4: Decorator-Only Approach**
- **What:** Put all Langfuse logic in decorators; no separate instrumentation module
- **Why we ruled it out:** Decorators alone can't manage session lifecycle or guarantee flushing. We need a module to coordinate init/flush at the hook boundaries.

---

## Part 4: Detailed Implementation Plan

### Files to Create

**1. `.claude/plugin-generated/src/langfuse_instrumentation.py`**

**Rationale:** Central module for all Langfuse lifecycle management. Extracts Claude/Gemini session ID, manages session trace initialization, creates child spans for each prompt, and ensures proper cleanup.

**Responsibilities:**
- `init_langfuse_trace(project_root)` — Set up session-level trace using `CLAUDE_SESSION_ID` or `GEMINI_SESSION_ID` from environment
- `init_langfuse_prompt_span(prompt_text)` — Create a child span for the current prompt
- `ensure_flush()` — Flush Langfuse traces (explicit, synchronous)
- Helper: Extract session ID from environment with fallback to parent PID

### Files to Update

**2. `.claude/plugin-generated/hooks/prompt_classifier.py`**

**Rationale:** This is the hook entry point. It must initialize the session trace before any operations, and flush after all operations complete.

**Changes:**
- Import `langfuse_instrumentation`
- After parsing `project_root` (line ~29), call `init_langfuse_trace(project_root)`
- After parsing `prompt` (line ~28), call `init_langfuse_prompt_span(prompt)`
- At the very end (before `sys.exit(0)`), call `ensure_flush()`
- Remove lines 45-47: Manual `LANGFUSE_TRACE_ID` assignment (now handled by instrumentation module)
- Remove line 66: Manual `langfuse_context.flush()` call (now handled by `ensure_flush()`)

**3. `.claude/plugin-generated/src/llm_client.py`**

**Rationale:** Make span naming explicit so Langfuse UI clearly shows this is an LLM generation operation.

**Changes:**
- Line 8: Change `@observe(as_type="generation")` to `@observe(name="query_llm", as_type="generation")`
- No logic changes; purely adding explicit naming

**4. `.claude/plugin-generated/src/dispatcher.py`**

**Rationale:** Make span naming explicit so Langfuse UI clearly shows this is a dispatch/routing operation.

**Changes:**
- Find the `dispatch_agent()` method and its `@observe` decorator
- Add `name="dispatch_agent"` parameter to the decorator
- No logic changes; purely adding explicit naming

### Implementation Tasks (TDD Flow)

**Task 1: Write the instrumentation module**
1. Write failing test for `init_langfuse_trace()` with mock Langfuse context
2. Implement `init_langfuse_trace()` to extract session ID and update Langfuse context
3. Write failing test for `init_langfuse_prompt_span()`
4. Implement `init_langfuse_prompt_span()` to create a named child span
5. Write failing test for `ensure_flush()`
6. Implement `ensure_flush()` to call `langfuse_context.flush()`
7. Verify all tests pass

**Task 2: Update prompt_classifier.py hook**
1. Add imports for the new instrumentation module
2. Add call to `init_langfuse_trace()` after project_root is resolved
3. Add call to `init_langfuse_prompt_span(prompt)` after prompt is extracted
4. Add call to `ensure_flush()` before `sys.exit(0)`
5. Remove manual trace ID initialization (lines 45-47)
6. Remove manual flush call (line 66)
7. Run hook manually and verify it executes without errors

**Task 3: Update llm_client.py decorator**
1. Add explicit `name="query_llm"` to the `@observe()` decorator
2. Verify decorator syntax is correct

**Task 4: Update dispatcher.py decorator**
1. Find `dispatch_agent()` method and its `@observe` decorator
2. Add explicit `name="dispatch_agent"` to the decorator
3. Verify decorator syntax is correct

**Task 5: Integration test**
1. Submit a test prompt through Claude Code and verify it reaches Langfuse
2. Check Langfuse UI: confirm one session trace with child spans for each prompt (if multiple prompts in same session)
3. Verify span names are readable: "dispatch_agent", "query_llm"
4. Verify session ID matches the Claude Code session

---

## Summary

This refactor centralizes Langfuse instrumentation into a single module that:
- Manages session-level tracing without state persistence
- Uses Claude/Gemini session IDs automatically
- Provides explicit, readable span names
- Guarantees trace cleanup at hook boundaries
- Removes duplication across hook, dispatcher, and LLM client
