# Langfuse v4 Upgrade Design Document

**Date:** 2026-05-27  
**Status:** Design Complete - Ready for Implementation  
**Priority:** High - Unblocks observability in Claude Code

---

## Section 0: Problem Understanding

**The Business Problem:**

The Langfuse observability integration in the Agentic Harness is currently broken for Claude Code because the code was written for Langfuse v4 API, but only v2.60.10 is installed. Specifically:

1. **Current State:** The harness has instrumentation code (observers, decorators, trace initialization) but it's only partially functional:
   - `langfuse_instrumentation.py` tries to import `get_client()` which doesn't exist in v2 → silent failure
   - `dispatcher.py` and `llm_client.py` work partially with `langfuse_context` which exists in v2
   - Traces never reach the Langfuse dashboard because initialization is broken

2. **Why This Matters:** Without working observability:
   - Cannot trace agent execution flows through Claude Code
   - Cannot see LLM call details, latencies, or failures in Langfuse
   - No session tracking across agent dispatches
   - Cannot debug or monitor system behavior in production

3. **The Solution:** Upgrade to Langfuse v4 to:
   - Use modern, actively maintained APIs
   - Enable proper distributed tracing across the harness ecosystem
   - Get better observability features (v4 has improvements over v2)
   - Future-proof the codebase

4. **Scope:** Update 6 files across src/harness and .claude/plugin-generated (dispatcher, llm_client, langfuse_instrumentation, hooks), update dependency constraint in pyproject.toml, and ensure end-to-end tracing works.

---

## Section 1: Technical Plan

**High-Level Implementation Overview:**

The upgrade will modernize how tracing flows through the harness in three layers:

**Layer 1: Dependency Management**
- Update `pyproject.toml` to `langfuse>=4.0.0` (instead of `>=2.50.0,<3.0.0`)
- This gives us access to v4 APIs: the `get_client()` singleton, improved context management, and better structured observations

**Layer 2: Instrumentation Module** 
- Update `langfuse_instrumentation.py` in both locations (src/harness/runtime and .claude/plugin-generated/src) to use v4 APIs
- Instead of `Langfuse()` constructor calls, use v4's `get_client()` to get a singleton client
- Keep the same public interface (`init_langfuse_trace`, `init_langfuse_prompt_span`, `ensure_flush`) so nothing else breaks

**Layer 3: Dispatcher & LLM Client**
- The v2 code in `dispatcher.py` and `llm_client.py` already uses `langfuse_context` which should be compatible with v4
- Minor adjustments may be needed if v4's context API differs, but likely minimal
- The hook in `prompt_classifier.py` already has a graceful fallback, so it should work with v4

**Ecosystem Integration:**
- All agent traces (from Claude Code, Gemini CLI, etc.) will route through the same `langfuse_instrumentation` module
- Session IDs will be consistent (pulled from `CLAUDE_SESSION_ID`, `GEMINI_SESSION_ID`, etc.)
- Traces will automatically appear in your Langfuse dashboard with proper parent-child relationships

**End-to-End Flow:**
1. User submits prompt to Claude Code
2. `prompt_classifier.py` hook initializes trace with `init_langfuse_trace()`
3. Dispatcher routes to agent, `@observe` decorator creates child spans
4. LLM client captures query details with `langfuse_context.update_current_observation()`
5. On exit, `ensure_flush()` ensures all traces are sent to Langfuse backend
6. Traces appear in Langfuse dashboard with full session context

---

## Section 2: Alternatives Considered

**Alternative 1: Keep Langfuse v2 and Fix the Code**
- **What it means:** Update `langfuse_instrumentation.py` to use Langfuse v2's `Langfuse()` class instead of v4's `get_client()`
- **Why we ruled it out:** 
  - v2 is no longer actively maintained; v4 is the current stable release
  - Adds technical debt—future team members expect modern APIs
  - Missing v4 features (better context management, improved span attributes, etc.)
  - Would require defending the v2 dependency choice later
  - This is a one-time migration effort; delaying it only pushes cost to the future

**Alternative 2: Pin to a Specific v4 Version (e.g., `langfuse==4.0.0`)**
- **What it means:** Instead of `langfuse>=4.0.0,<5.0.0`, use an exact pin
- **Why we ruled it out:**
  - Locks out security patches and bug fixes
  - Makes dependency updates harder in the future (requires explicit version bumps)
  - Version ranges are standard Python practice for stable APIs
  - v4's public API is stable; minor version updates are safe

**Alternative 3: Gradual v2→v4 Coexistence (Dual-Support)**
- **What it means:** Support both v2 and v4 APIs simultaneously with feature flags
- **Why we ruled it out:**
  - Over-engineered—adds complexity with no real benefit
  - Would require maintaining branching logic in every instrumentation call
  - Tests become harder to reason about (which version are we testing?)
  - Clean cutover is simpler and faster than gradual migration

**Alternative 4: Replace Langfuse with a Different Observability Tool**
- **What it means:** Switch to OpenTelemetry, Datadog, or similar
- **Why we ruled it out:**
  - Langfuse already integrated and working (partial functionality)
  - Switching tools would require rewriting all instrumentation from scratch
  - v4 upgrade is lower-cost than a complete tool migration
  - Team already familiar with Langfuse

---

## Section 3: Detailed Implementation Plan

**All files that will be changed or created:**

### Dependency & Configuration
1. **pyproject.toml**
   - Rationale: Update Langfuse constraint from `langfuse>=2.50.0,<3.0.0` to `langfuse>=4.0.0,<5.0.0`
   - This enables v4 APIs across the entire project

### Core Instrumentation Files (Must Update - Same changes in both locations)
2. **src/harness/runtime/langfuse_instrumentation.py**
   - Rationale: Replace `from langfuse import Langfuse` (v2 class) with `from langfuse import get_client` (v4 singleton). Update `_get_session_id()`, `_is_client_active()`, `init_langfuse_trace()`, `init_langfuse_prompt_span()`, and `ensure_flush()` to use v4 APIs.
   - This is the main broken module that needs v4 support

3. **.claude/plugin-generated/src/langfuse_instrumentation.py**
   - Rationale: Apply identical changes as file #2 (these are synced copies)

### Dispatcher & LLM Client (May need minor adjustments)
4. **src/harness/runtime/dispatcher.py**
   - Rationale: Check if `langfuse_context` API is compatible with v4. May need to adjust how `langfuse_context.update_current_observation(model=...)` is called if v4 changes the signature
   - Likely minimal changes or none needed (v4 usually maintains API stability)

5. **src/harness/runtime/llm_client.py**
   - Rationale: Check v4 compatibility of `langfuse_context.update_current_trace()` and `langfuse_context.update_current_observation()` calls
   - Likely minimal changes

6. **.claude/plugin-generated/src/dispatcher.py**
   - Rationale: Same as file #4 (synced copy)

7. **.claude/plugin-generated/src/llm_client.py**
   - Rationale: Same as file #5 (synced copy)

### Hooks
8. **.claude/plugin-generated/hooks/prompt_classifier.py**
   - Rationale: Already has graceful fallback for `observe` decorator. Verify `langfuse_instrumentation` module imports work with v4. May need to adjust import error handling if module structure changes

### Test Files (Must Update)
9. **tests/unit/test_dispatcher.py**
   - Rationale: Update mock patches if v4 changes where `langfuse_context` is defined (e.g., if it moves from `langfuse.decorators` to another module). Re-run all 20 tests to ensure they still pass with v4

10. **.claude/plugin-generated/tests/test_langfuse_instrumentation.py**
    - Rationale: Update all test mocks and assertions for v4 API. Tests currently patch `get_client` as `None`; will need to patch v4's actual `get_client()` function. Verify all 19 tests pass with v4

### New Files (Optional - for end-to-end validation)
11. **tests/integration/test_langfuse_e2e.py** (NEW - if creating integration test)
    - Rationale: Create integration test that:
      - Initializes trace with real/mock Langfuse credentials
      - Calls `dispatcher.classify_intent()` to trigger tracing
      - Verifies trace was queued/sent to Langfuse backend
      - Validates session ID and span structure in response
    - This confirms end-to-end tracing works after upgrade

---

## Task Breakdown (TDD - Red/Green/Refactor)

**Phase 1: Setup**
- Update `pyproject.toml` with v4 dependency
- Install v4: `pip install -U langfuse>=4.0.0`

**Phase 2: Instrumentation Module** (TDD for each function)
- Write failing test for `init_langfuse_trace()` with v4 API
- Update `langfuse_instrumentation.py` to import v4's `get_client`
- Watch test pass
- Repeat for `init_langfuse_prompt_span()` and `ensure_flush()`
- Update `.claude/plugin-generated/src/langfuse_instrumentation.py` identically

**Phase 3: Dispatcher & LLM Client Compatibility**
- Run existing dispatcher tests to check for v4 breakage
- Fix any compatibility issues (likely in mocking, not business logic)
- Run existing llm_client tests
- Fix any compatibility issues

**Phase 4: Hook Verification**
- Run prompt_classifier hook end-to-end to ensure Langfuse calls work
- Adjust import fallback if needed

**Phase 5: Integration Testing** (if creating new test)
- Write failing integration test (`test_langfuse_e2e.py`)
- Mock or use real Langfuse credentials to test actual trace flow
- Verify traces appear in correct format

---

## Success Criteria

- ✓ All 20 unit tests in `test_dispatcher.py` pass with v4
- ✓ All 19 unit tests in `test_langfuse_instrumentation.py` pass with v4
- ✓ Traces from Claude Code appear in Langfuse dashboard
- ✓ Session IDs are consistent across multiple prompts
- ✓ Span hierarchy is correct (parent/child relationships visible)
- ✓ No errors or warnings in instrumentation logs

---

## Dependencies

- Langfuse v4 (currently v2.60.10)
- Python 3.11+ (likely already supported by v4)
- No new external dependencies required
