# Langfuse Instrumentation Refactor — Progress Tracking

**Design Document:** `2026-05-27-langfuse-refactor-design.md`  
**Status:** In Design → Ready for Implementation  
**Last Updated:** 2026-05-27

---

## Task Breakdown

### Task 1: Write the instrumentation module
- **File:** `.claude/plugin-generated/src/langfuse_instrumentation.py`
- **Status:** [ ] Pending
- **Subtasks:**
  - [ ] Write failing test for `init_langfuse_trace()` with mock Langfuse context
  - [ ] Implement `init_langfuse_trace()` to extract session ID and update Langfuse context
  - [ ] Write failing test for `init_langfuse_prompt_span()`
  - [ ] Implement `init_langfuse_prompt_span()` to create a named child span
  - [ ] Write failing test for `ensure_flush()`
  - [ ] Implement `ensure_flush()` to call `langfuse_context.flush()`
  - [ ] Verify all tests pass

### Task 2: Update prompt_classifier.py hook
- **File:** `.claude/plugin-generated/hooks/prompt_classifier.py`
- **Status:** [ ] Pending
- **Subtasks:**
  - [ ] Add imports for the new instrumentation module
  - [ ] Add call to `init_langfuse_trace()` after project_root is resolved
  - [ ] Add call to `init_langfuse_prompt_span(prompt)` after prompt is extracted
  - [ ] Add call to `ensure_flush()` before `sys.exit(0)`
  - [ ] Remove manual trace ID initialization (lines 45-47)
  - [ ] Remove manual flush call (line 66)
  - [ ] Run hook manually and verify it executes without errors

### Task 3: Update llm_client.py decorator
- **File:** `.claude/plugin-generated/src/llm_client.py`
- **Status:** [ ] Pending
- **Subtasks:**
  - [ ] Add explicit `name="query_llm"` to the `@observe()` decorator
  - [ ] Verify decorator syntax is correct

### Task 4: Update dispatcher.py decorator
- **File:** `.claude/plugin-generated/src/dispatcher.py`
- **Status:** [ ] Pending
- **Subtasks:**
  - [ ] Find `dispatch_agent()` method and its `@observe` decorator
  - [ ] Add explicit `name="dispatch_agent"` to the decorator
  - [ ] Verify decorator syntax is correct

### Task 5: Integration test
- **Status:** [ ] Pending
- **Subtasks:**
  - [ ] Submit a test prompt through Claude Code and verify it reaches Langfuse
  - [ ] Check Langfuse UI: confirm one session trace with child spans for each prompt
  - [ ] Verify span names are readable: "dispatch_agent", "query_llm"
  - [ ] Verify session ID matches the Claude Code session

---

## Notes

- **TDD Approach:** Each task follows Red → Green → Refactor
- **No State Persistence:** Session tracking relies on `CLAUDE_SESSION_ID` env var
- **Zero Breaking Changes:** Existing code continues to work; decorators become more explicit
