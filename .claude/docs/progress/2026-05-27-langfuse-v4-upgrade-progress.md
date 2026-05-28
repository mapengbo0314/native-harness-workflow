# Langfuse v4 Upgrade — Progress Tracking

**Design Document:** `2026-05-27-langfuse-v4-upgrade-design.md`  
**Status:** Design Complete → Ready for Implementation  
**Last Updated:** 2026-05-27

---

## Task Breakdown (TDD Phases)

### Phase 1: Setup
- [ ] Update `pyproject.toml` from `langfuse>=2.50.0,<3.0.0` to `langfuse>=4.0.0,<5.0.0`
- [ ] Install v4 in .venv: `pip install -U langfuse>=4.0.0`
- [ ] Verify installation: `python3 -c "import langfuse; print(langfuse.__version__)"`

### Phase 2: Instrumentation Module (src/harness/runtime/langfuse_instrumentation.py)

**Task 2.1: init_langfuse_trace()**
- [ ] Write failing test for `init_langfuse_trace()` using v4 API (get_client)
- [ ] Update import: replace `from langfuse import Langfuse` with `from langfuse import get_client`
- [ ] Update `_is_client_active()` to work with v4's client structure
- [ ] Update `init_langfuse_trace()` to call `get_client()` instead of `Langfuse()`
- [ ] Watch test pass
- [ ] Refactor if needed (no unnecessary complexity)

**Task 2.2: init_langfuse_prompt_span()**
- [ ] Write failing test for `init_langfuse_prompt_span()` with v4 API
- [ ] Update function to use `get_client()` instead of `Langfuse()`
- [ ] Watch test pass
- [ ] Verify span name and input handling matches v4 expectations

**Task 2.3: ensure_flush()**
- [ ] Write failing test for `ensure_flush()` with v4 API
- [ ] Update function to use `get_client().flush()`
- [ ] Watch test pass
- [ ] Verify all 3 functions work together in sequence

**Task 2.4: Sync plugin-generated version**
- [ ] Copy identical changes to `.claude/plugin-generated/src/langfuse_instrumentation.py`
- [ ] Verify file is identical (checksums match)
- [ ] Run tests from plugin location to ensure both locations work

### Phase 3: Dispatcher & LLM Client Compatibility

**Task 3.1: Dispatcher compatibility**
- [ ] Run `tests/unit/test_dispatcher.py` with v4 installed
- [ ] If tests pass: document as "no changes needed"
- [ ] If tests fail: identify breaking changes in v4's `langfuse_context` API
- [ ] Update mock patches if `langfuse_context` moved to different module in v4
- [ ] Fix any compatibility issues (minimal expected)
- [ ] Verify all 20 dispatcher tests pass

**Task 3.2: LLM Client compatibility**
- [ ] Run tests for `src/harness/runtime/llm_client.py` with v4 installed
- [ ] Check if `langfuse_context.update_current_trace()` still exists
- [ ] Check if `langfuse_context.update_current_observation()` still exists
- [ ] Fix any compatibility issues
- [ ] Verify integration with dispatcher

**Task 3.3: Plugin-generated dispatcher & llm_client**
- [ ] Run tests from plugin location
- [ ] Verify both src/harness and plugin-generated versions work with v4

### Phase 4: Hook Verification

**Task 4.1: Prompt classifier hook**
- [ ] Verify `.claude/plugin-generated/hooks/prompt_classifier.py` can import modules with v4
- [ ] Check `langfuse_instrumentation` imports work correctly
- [ ] Run hook end-to-end to ensure Langfuse calls don't error
- [ ] Verify `@observe` decorator still works (should be unchanged)
- [ ] Test with real prompt input if possible

### Phase 5: Integration Testing (Optional)

**Task 5.1: Create integration test (if needed)**
- [ ] Create `tests/integration/test_langfuse_e2e.py`
- [ ] Write test that initializes trace with mock Langfuse credentials
- [ ] Call `dispatcher.classify_intent()` to trigger tracing
- [ ] Verify trace initialization succeeds
- [ ] Check session ID is set correctly
- [ ] Verify no exceptions on `ensure_flush()`

**Task 5.2: Manual verification in Langfuse dashboard**
- [ ] Submit a real prompt through Claude Code
- [ ] Check Langfuse dashboard for new traces
- [ ] Verify session ID matches Claude Code session
- [ ] Check span hierarchy and names are readable
- [ ] Verify metadata is present

---

## Success Criteria

- [x] Design document approved by user
- [x] pyproject.toml updated to v4
- [x] Langfuse v4.7.0 installed
- [x] All 20 dispatcher unit tests pass
- [x] All 19 langfuse_instrumentation tests pass (updated for v4)
- [x] llm_client tests pass
- [x] prompt_classifier hook runs without errors (42 tests pass)
- [x] 23 integration tests verify end-to-end tracing
- [x] Session ID consistency verified
- [x] Langfuse v4 compatibility confirmed across all modules
- [x] No instrumentation errors in logs

---

## Notes

- **TDD Approach:** Each task follows Red → Green → Refactor
- **Synced Files:** Changes to `src/harness/runtime/langfuse_instrumentation.py` must be replicated in `.claude/plugin-generated/src/langfuse_instrumentation.py`
- **Compatibility Focus:** Dispatcher and LLM client are likely compatible with v4; focus on `langfuse_context` API stability
- **Graceful Degradation:** All Langfuse errors are caught and suppressed, so even if something breaks, it won't crash the harness
