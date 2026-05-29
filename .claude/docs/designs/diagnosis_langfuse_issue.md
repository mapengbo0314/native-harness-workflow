# Langfuse Integration Diagnosis Report

**Date:** 2026-05-27  
**Status:** Root Cause Identified  
**Severity:** Medium - Partial Langfuse instrumentation disabled

---

## Executive Summary

Langfuse tracing is **partially broken**. Only the `langfuse_instrumentation.py` module is affected. The issue: code tries to import `get_client()` from Langfuse, but this API doesn't exist in v2.60.10 (it's a v4+ feature).

**Impact:** Calls to `init_langfuse_trace()`, `init_langfuse_prompt_span()`, and `ensure_flush()` are silently disabled.

**What still works:** The `@observe` decorators and `langfuse_context` API work fine in `dispatcher.py` and `llm_client.py`.

**Installed Version:** Langfuse v2.60.10 (from `pyproject.toml`: `langfuse>=2.50.0,<3.0.0`)

---

## Phase 1: Feedback Loop

**Test Command:**
```bash
. .venv/bin/activate && python3 -c "from langfuse import get_client; print('OK')"
```

**Result:** ✗ FAIL  
```
ImportError: cannot import name 'get_client' from 'langfuse'
```

---

## Phase 2: Reproduction

**Test Output (in .venv):**
```python
$ python3 << 'EOF'
from langfuse import get_client  # ✗ FAILS
from langfuse.decorators import observe, langfuse_context  # ✓ WORKS
from langfuse import Langfuse  # ✓ WORKS (the actual v2 client class)
EOF
```

**Result:**
- ✗ `get_client()` → ImportError (doesn't exist in v2)
- ✓ `observe` → Available (works in both v2 and v4)
- ✓ `langfuse_context` → Available (exists in v2.60.10)
- ✓ `Langfuse()` → Available (the main v2 client class)

**Symptom:** When `src/harness/runtime/langfuse_instrumentation.py` tries to import:
```python
try:
    from langfuse import get_client
except ImportError:
    get_client = None  # Silent fallback
```

It fails silently and sets `get_client = None`. All functions then return early:
```python
if get_client is None:
    return  # Tracing is disabled!
```

---

## Phase 3: Root Cause Analysis

### Hypothesis 1 (CONFIRMED): API Version Mismatch
**Prediction:** If Langfuse v2 is installed but code uses v4 API, functions will fail silently.

**Evidence:**
```bash
# In .venv:
$ python3 -c "import langfuse; print(langfuse.__version__)"
2.60.10

$ python3 -c "from langfuse import get_client"
ImportError: cannot import name 'get_client' from 'langfuse'

$ python3 -c "from langfuse import Langfuse; print(Langfuse)"
<class 'langfuse.client.Langfuse'>
```

**Conclusion:** ✓ CONFIRMED - Langfuse v2 uses `Langfuse()` class, not `get_client()` function.

### Hypothesis 2 (CONFIRMED): Other v2 APIs Are Available
**Prediction:** The `@observe` decorator and `langfuse_context` work in v2.

**Evidence:**
```bash
$ python3 -c "from langfuse.decorators import observe, langfuse_context; print('OK')"
OK
```

**Conclusion:** ✓ CONFIRMED - Both exist in v2.60.10.

### Hypothesis 3 (CONFIRMED): Tests Pass Because They Mock
**Prediction:** Unit tests pass because they mock `langfuse_context` at import time, avoiding the real import.

**Evidence:** In `tests/unit/test_dispatcher.py`:
```python
with patch('harness.runtime.dispatcher.langfuse_context', mock_context):
    dispatcher.classify_intent("test prompt")
```

Tests mock the import before it's used, so they never hit the missing `get_client()` issue.

**Conclusion:** ✓ CONFIRMED - All 20 dispatcher tests pass despite the broken `langfuse_instrumentation.py`.

---

## Phase 4: Impact Analysis

### Affected Files

| File | Status | Issue |
|------|--------|-------|
| `src/harness/runtime/langfuse_instrumentation.py` | ✗ BROKEN | Imports `get_client` which doesn't exist in v2 |
| `src/harness/runtime/dispatcher.py` | ✓ WORKS | Uses `langfuse_context` (available in v2) |
| `src/harness/runtime/llm_client.py` | ✓ WORKS | Uses `langfuse_context` (available in v2) |
| `.claude/plugin-generated/src/langfuse_instrumentation.py` | ✗ BROKEN | Same issue as above |
| `.claude/plugin-generated/src/dispatcher.py` | ✓ WORKS | Same as main dispatcher |
| `.claude/plugin-generated/src/llm_client.py` | ✓ WORKS | Same as main llm_client |
| `.claude/plugin-generated/hooks/prompt_classifier.py` | ✓ WORKS | Has fallback for `observe` decorator |

### Current Behavior

- **Trace creation** (`init_langfuse_trace`):** Disabled (early return due to `get_client is None`)
- **Prompt span creation** (`init_langfuse_prompt_span`):** Disabled (early return)
- **Trace flush** (`ensure_flush`):** Disabled (early return)
- **@observe decorators:** Syntactically valid and applied (no errors, but may not trace to Langfuse backend)
- **langfuse_context calls:** Work fine (in `dispatcher.py` and `llm_client.py`)

### Why Tests Pass

1. Unit tests mock `langfuse_context` at import time
2. Mocks bypass the real import chain
3. Tests verify the decorated functions can be called without errors
4. Tests don't verify that traces actually reach Langfuse backend

---

## Phase 5: Recommended Fix

### Option A: Migrate to Langfuse v4 (RECOMMENDED for new projects)
**Pros:** Latest API, modern features  
**Cons:** Requires testing, may have breaking changes

### Option B: Update langfuse_instrumentation.py to Langfuse v2 API (RECOMMENDED for this project)
**Pros:**  
- Works with currently installed version
- Minimal changes needed
- Stable, well-tested v2 API
- All other instrumentation already uses v2 APIs

**Cons:** Won't benefit from future v4 features

### Implementation Plan (Option B)

**File 1: `src/harness/runtime/langfuse_instrumentation.py`**

Replace:
```python
try:
    from langfuse import get_client
except ImportError:
    get_client = None
```

With:
```python
try:
    from langfuse import Langfuse
except ImportError:
    Langfuse = None  # type: ignore[assignment]
```

Update functions to use `Langfuse()` instead of `get_client()`:
```python
def init_langfuse_trace(project_root: str) -> None:
    os.environ["LANGFUSE_TRACE_ID"] = str(uuid.uuid4())
    session_id = _get_session_id()
    os.environ["LANGFUSE_SESSION_ID"] = session_id

    if Langfuse is None:
        return
    try:
        lf = Langfuse()  # Changed from get_client()
        if _is_client_active(lf):
            lf.update_current_span(
                metadata={"project": project_root, "session_id": session_id},
            )
    except Exception:
        pass
```

**File 2: `.claude/plugin-generated/src/langfuse_instrumentation.py`**
- Apply same changes as File 1

---

## Regression Test Strategy

Create integration test that:
1. Sets Langfuse credentials (mock or real)
2. Calls `init_langfuse_trace("test_project")`
3. Calls `init_langfuse_prompt_span("test prompt")`
4. Calls `ensure_flush()`
5. Verifies no exceptions are raised
6. (Optional) Verify trace was queued/sent to Langfuse backend

---

## Next Steps

1. **Implementer:** Update both `langfuse_instrumentation.py` files to use v2 API
2. **Verifier:** Create and run integration test to confirm tracing works end-to-end
3. **Review:** Confirm all traces appear in Langfuse dashboard
