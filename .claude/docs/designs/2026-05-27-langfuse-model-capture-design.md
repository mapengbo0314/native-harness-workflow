# Langfuse Model Capture Fix — Design Document

## Problem
Langfuse is always recording "2.5-flash" as the model because the @observe decorators don't capture the actual model being used at runtime. The model is determined at execution time but not passed to Langfuse.

## Solution
Add `langfuse_context.update_current_span(model=model)` calls in each dispatcher method to capture the actual model from the environment variables after the decorator creates the span.

## Scope
Fix three dispatcher files:
1. `.claude/plugin-generated/src/dispatcher.py` — Claude version
2. `src/harness/runtime/dispatcher.py` — Runtime version
3. `src/harness/dispatcher.py` — Harness template version

## Tasks

### Task 1: Fix Claude dispatcher (.claude/plugin-generated/src/dispatcher.py)
**Status:** Pending

**Changes needed:**
- The @observe decorators already have explicit names (`@observe(name="classify_intent", ...)`) — keep as-is
- Add `langfuse_context.update_current_span(model=model)` in `classify_intent()` after determining the model (line 113)
- Add `langfuse_context.update_current_span(model=model)` in `dispatch_agent()` early in the method to capture the model being used

**Files:** `.claude/plugin-generated/src/dispatcher.py`

---

### Task 2: Fix Runtime dispatcher (src/harness/runtime/dispatcher.py)
**Status:** Pending

**Changes needed:**
- Update `@observe(as_type="span")` on line 75 to `@observe(name="classify_intent", as_type="span")`
- Update `@observe()` on line 248 to `@observe(name="dispatch_agent")`
- Add `langfuse_context.update_current_span(model=model)` in `classify_intent()` after determining the model (line 113)
- Add `langfuse_context.update_current_span(model=model)` in `dispatch_agent()` early in the method to capture the model being used

**Files:** `src/harness/runtime/dispatcher.py`

---

### Task 3: Add Langfuse to Harness template (src/harness/dispatcher.py)
**Status:** Pending

**Changes needed:**
- Add Langfuse imports: `from langfuse.decorators import observe, langfuse_context`
- Add @observe decorators to classify_intent() and dispatch_agent() methods
- Add `langfuse_context.update_current_span(model=model)` calls in both methods
- Handle the fact that this template version may not have all the same context setup as runtime version

**Files:** `src/harness/dispatcher.py`

---

## Implementation Details

### Model Capture Pattern
In both `classify_intent()` and `dispatch_agent()`:
```python
# Determine which model will be used
if api_key:
    model = os.environ.get("HARNESS_MODEL", "gemini-2.5-flash-lite")
else:
    model = os.environ.get("HARNESS_PLATFORM_CLI", "claude")  # fallback to CLI name

# Tell Langfuse which model is actually being used
langfuse_context.update_current_span(model=model)
```

### Reference Implementation
See `.claude/plugin-generated/src/dispatcher.py` as the reference for what should be in the final state.

## Testing
- Verify @observe decorators have explicit names
- Verify langfuse_context.update_current_span(model=...) is called in both methods
- Verify model is determined from environment variables
- Run any existing tests to ensure no regressions

## Acceptance Criteria
✅ All three files have @observe decorators with explicit names
✅ All three files call langfuse_context.update_current_span(model=...) in both decorator methods
✅ Model is captured from environment variables (HARNESS_MODEL or HARNESS_PLATFORM_CLI)
✅ No syntax errors or import issues
✅ Existing tests pass
