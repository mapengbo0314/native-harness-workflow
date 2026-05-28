# Langfuse Instrumentation Refactor — Progress Tracking

**Design Document:** `2026-05-27-langfuse-refactor-design.md`  
**Status:** In Design → Ready for Implementation  
**Last Updated:** 2026-05-27

---

## Task Breakdown

### Task 1: Write the instrumentation module
- **File:** `.claude/plugin-generated/src/langfuse_instrumentation.py`
- **Status:** [x] Complete — Updated 2026-05-27 (v4 API fix)
- **Subtasks:**
  - [x] Write failing test for `init_langfuse_trace()` with mock Langfuse context
  - [x] Implement `init_langfuse_trace()` to extract session ID and update Langfuse context
  - [x] Write failing test for `init_langfuse_prompt_span()`
  - [x] Implement `init_langfuse_prompt_span()` to create a named child span
  - [x] Write failing test for `ensure_flush()`
  - [x] Implement `ensure_flush()` to call `langfuse_context.flush()`
  - [x] Verify all tests pass — 14/14 passing
- **Note (Task 2 finding):** Original module used `from langfuse.decorators import langfuse_context` which
  does not exist in Langfuse v4.7.0 (installed). Module was updated to use `from langfuse import get_client`
  (v4 API). Tests updated to patch `langfuse_instrumentation.get_client`. 14/14 still passing.
- **Test file:** `.claude/plugin-generated/tests/test_langfuse_instrumentation.py`

### Task 2: Update prompt_classifier.py hook
- **File:** `.claude/plugin-generated/hooks/prompt_classifier.py`
- **Status:** [x] Complete — 2026-05-27
- **Subtasks:**
  - [x] Add `from langfuse import observe` import (v4 API; `langfuse.decorators` removed in v4)
  - [x] Add `import langfuse_instrumentation` after `sys.path` insert
  - [x] Add `@observe(name="user_prompt")` decorator on `main()`
  - [x] Call `init_langfuse_trace(str(project_root))` after path setup
  - [x] Call `init_langfuse_prompt_span(prompt)` after trace init
  - [x] Call `ensure_flush()` before `sys.exit(0)`
  - [x] Remove manual LANGFUSE_TRACE_ID assignment (was lines 45-47)
  - [x] Remove manual `langfuse_context.flush()` call (was line 66)
  - [x] Remove `import uuid` (no longer used)
  - [x] Hook verified: exits 0, prints valid JSON

### Task 3: Update llm_client.py decorator
- **File:** `.claude/plugin-generated/src/llm_client.py`
- **Status:** [x] Complete — 2026-05-27
- **Subtasks:**
  - [x] `@observe(name="query_llm", as_type="generation")` added to `query_llm`

### Task 4: Update dispatcher.py decorator
- **File:** `.claude/plugin-generated/src/dispatcher.py`
- **Status:** [x] Complete — 2026-05-27
- **Subtasks:**
  - [x] `@observe(name="dispatch_agent")` on `dispatch_agent`
  - [x] `@observe(name="classify_intent", as_type="span")` on `classify_intent`

### Task 5: Integration test
- **Status:** [ ] Pending — Manual verification required
- **Subtasks:**
  - [ ] Submit a real prompt through Claude Code and verify it reaches Langfuse
  - [ ] Check Langfuse UI: confirm one session trace with child spans per prompt
  - [ ] Verify span names are readable: "user_prompt", "dispatch_agent", "classify_intent", "query_llm"
  - [ ] Verify session ID matches the Claude Code session (`CLAUDE_SESSION_ID`)

---

## Notes

- **TDD Approach:** Each task follows Red → Green → Refactor
- **No State Persistence:** Session tracking relies on `CLAUDE_SESSION_ID` env var
- **Zero Breaking Changes:** Existing code continues to work; decorators become more explicit
