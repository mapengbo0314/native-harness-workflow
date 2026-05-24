# Design Doc

## Problem Statement
The current hook implementations have critical architectural flaws in their fail-safe mechanisms:
1. `JSONDecodeError` escapes the agent by returning `sys.exit(0)`, allowing malformed JSON to silently bypass security guards.
2. Inner `try/except` blocks swallow errors (like in `prompt_classifier.py` and `stop_verifier.py`), masking systemic failures.
3. `post_tool_observer.py` has a race condition where it re-reads the state immediately after updating it, which can fetch stale data.
4. `stop_verifier.py` is missing critical imports, leading to `NameError` crashes that exit 2 for the wrong reasons.
5. Error detection relies on brittle `"type"` matching instead of `"hook_event_name"`.
6. There is no automated test coverage for the circuit breaker.

## Proposed Design
We will rewrite the core logic of all hook templates to ensure robust error handling and tracking:
- Replace `sys.exit(0)` with `sys.exit(2)` on `JSONDecodeError` across all hooks.
- Remove all nested `try/except` blocks so unhandled exceptions correctly bubble up to the global `except Exception:` block, triggering a hard stop (`sys.exit(2)`).
- Use a closure/mutable variable (`captured_count = [0]`) in `post_tool_observer.py`'s `modifier` callback to capture the failure count atomically, eliminating the race condition.
- Add missing imports (`os`, `subprocess`, `Path`) to `stop_verifier.py`.
- Check `"hook_event_name"` for `PostToolUseFailure` in `post_tool_observer.py`.
- Introduce TDD steps to explicitly test the circuit breaker behavior in `tests/hooks/test_claude_hooks.py`.

## Alternatives
- *Alternative 1*: Use a synchronous file lock for state reading/writing. *Rejected* because the `update_state` function already handles atomicity; the issue was simply fetching the state again asynchronously instead of capturing the value during the atomic update.
- *Alternative 2*: Let the Orchestrator manage the circuit breaker. *Rejected* because the harness needs to be agent-agnostic and protect against any agent, including orchestrators.

## Sphinch Marks
- [x] `JSONDecodeError` triggers `sys.exit(2)` in all hooks.
- [x] Inner `try/except` blocks removed from `prompt_classifier.py`, `stop_verifier.py`, and `precompact_handoff.py`.
- [x] `post_tool_observer.py` uses `captured_count` within `modifier`.
- [x] `stop_verifier.py` imports `os`, `subprocess`, and `Path`.
- [x] `post_tool_observer.py` checks `hook_event_name == "PostToolUseFailure"`.
- [x] `tests/hooks/test_claude_hooks.py` contains tests injecting `consecutive_tool_failures: 3`.

---

# Circuit Breaker and Global Fail-Safes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Enforce strict fail-safes across all hook templates to ensure any crash or malformed JSON blocks the agent (`exit 2`), and implement a circuit breaker that hard-stops the agent after 3 consecutive tool failures.

**Architecture:** We wrap the `main()` function execution of all hook scripts in a `try...except Exception` block that prints to stderr and calls `sys.exit(2)`. For the circuit breaker, `post_tool_observer.py` will track `consecutive_tool_failures` safely using a closure. We will modify `pre_tool_guard.py` and `post_tool_observer.py` to trigger the circuit breaker (`exit 2`) when this count reaches 3.

**Tech Stack:** Python, JSON

---

### Task 1: Add Circuit Breaker to `post_tool_observer.py` and `pre_tool_guard.py`

**Files:**
- Modify: `src/harness/templates/boilerplate/hooks/post_tool_observer.py`
- Modify: `src/harness/templates/boilerplate/hooks/pre_tool_guard.py`

- [x] **Step 1: Update `post_tool_observer.py`**
Modify `src/harness/templates/boilerplate/hooks/post_tool_observer.py` to trigger the circuit breaker using a captured count and robust error detection:
```python
import sys
import json
from hook_common import resolve_state_path, update_state
# Implementer: Preserve any other existing imports/functions!

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        has_error = input_data.get("error") is not None or input_data.get("hook_event_name") == "PostToolUseFailure"
        
        state_path = resolve_state_path(input_data)
        captured_count = [0]
        
        def modifier(s):
            if "consecutive_tool_failures" not in s:
                s["consecutive_tool_failures"] = 0
                
            if has_error:
                s["consecutive_tool_failures"] += 1
            else:
                s["consecutive_tool_failures"] = 0
                
            captured_count[0] = s["consecutive_tool_failures"]
                
        update_state(state_path, modifier)
        
        # Check circuit breaker using captured count to avoid race condition
        if captured_count[0] >= 3:
            print("Error: Circuit breaker tripped! 3 consecutive tool failures detected.", file=sys.stderr)
            sys.exit(2)
            
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in post_tool_observer: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
```

- [x] **Step 2: Update `pre_tool_guard.py`**
Replace `main()` in `src/harness/templates/boilerplate/hooks/pre_tool_guard.py` ensuring `JSONDecodeError` exits 2:
```python
import sys
import json
from hook_common import resolve_state_path, read_json, update_state
# Implementer: Preserve existing helper functions like _candidate_paths and is_protected_path!

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)

        tool_name = input_data.get("tool_name") or input_data.get("toolName", "")
        tool_input = input_data.get("tool_input") or input_data.get("toolInput", {})
        
        if tool_name in ["Write", "Edit", "MultiEdit", "Bash", "run_shell_command", "write_file", "replace"]:
            for candidate in _candidate_paths(tool_input):
                if is_protected_path(candidate, input_data):
                    print(f"Error: Access to protected path '{candidate}' is blocked.", file=sys.stderr)
                    sys.exit(2)
                    
        # Check Circuit Breaker
        state_path = resolve_state_path(input_data)
        state = read_json(state_path)
        
        if state.get("consecutive_tool_failures", 0) >= 3:
            # Reset the counter before hard stopping to prevent permanent system deadlocks across agent restarts
            def reset_breaker(s):
                s["consecutive_tool_failures"] = 0
            update_state(state_path, reset_breaker)
            print("Error: Circuit breaker tripped! 3 consecutive tool failures detected. Hard stopping agent.", file=sys.stderr)
            sys.exit(2)
            
        if tool_name in ["Task", "Agent", "generalist", "planner", "verifier"]:
            if state.get("current_branch") == "Branch D":
                prompt = str(tool_input).lower()
                if "explicit" not in prompt:
                    print("Error: Planner/verifier escalation blocked in Branch D unless explicit.", file=sys.stderr)
                    sys.exit(2)
                    
        # If passed
        print(json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}}))
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in pre_tool_guard: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
```

### Task 2: Apply Global Fail-Safe to remaining hooks

**Files:**
- Modify: `src/harness/templates/boilerplate/hooks/config_change_guard.py`
- Modify: `src/harness/templates/boilerplate/hooks/precompact_handoff.py`
- Modify: `src/harness/templates/boilerplate/hooks/prompt_classifier.py`
- Modify: `src/harness/templates/boilerplate/hooks/stop_verifier.py`

- [x] **Step 1: Update `config_change_guard.py`**
Replace `main()` in `src/harness/templates/boilerplate/hooks/config_change_guard.py` to fix the JSON exit code:
```python
import sys
import json
from hook_common import resolve_state_path, read_json, update_state
# Implementer: Preserve any other existing imports/functions!

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        state_path = resolve_state_path(input_data)
        state = read_json(state_path)
        
        if not state.get("maintenance_mode", False):
            print("Error: Config changes blocked. Enable maintenance_mode in state.", file=sys.stderr)
            sys.exit(2)
            
        def modifier(s):
            if "config_changes" not in s:
                s["config_changes"] = []
            s["config_changes"].append(input_data)
            
        update_state(state_path, modifier)
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in config_change_guard: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
```

- [x] **Step 2: Update `precompact_handoff.py`**
Replace `main()` in `src/harness/templates/boilerplate/hooks/precompact_handoff.py` to remove nested `try/except` and fix JSON parsing:
```python
import sys
import json
from hook_common import resolve_state_path, read_json, resolve_project_root, update_state
# Implementer: Preserve any other existing imports/functions!

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        state_path = resolve_state_path(input_data)
        state = read_json(state_path)
        
        project_root = resolve_project_root(input_data)
        handoff_path = project_root / "HANDOFF.md"
        
        goal = state.get("goal", "Unknown Goal")
        progress = state.get("progress", "Unknown Progress")
        next_steps = state.get("next_steps", "Unknown Next Steps")
        
        content = f"# HANDOFF\n\n## Goal\n{goal}\n\n## Progress\n{progress}\n\n## Next Steps\n{next_steps}\n"
        
        # Inner try block removed. IO errors will correctly bubble to the global exception handler
        with open(handoff_path, "w") as f:
            f.write(content)
            
        def modifier(s):
            s["handoff_written"] = True
            
        update_state(state_path, modifier)
        
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in precompact_handoff: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
```

- [x] **Step 3: Update `prompt_classifier.py`**
Replace `main()` in `src/harness/templates/boilerplate/hooks/prompt_classifier.py` to remove nested `try/except` around state update:
```python
import sys
import json
from hook_common import resolve_state_path, update_state
# Implementer: Note that `classify` is already defined in this file. Preserve it! Don't import from classifier_logic.

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        prompt = input_data.get("prompt", "")
        branch = classify(prompt)
        
        def modifier(state):
            state["current_branch"] = branch
            state["last_prompt"] = prompt[:100]
            
        state_path = resolve_state_path(input_data)
        
        # Inner try block removed. Errors will trigger the global exception block.
        update_state(state_path, modifier)
            
        # Output compact labels/reasons only
        print(json.dumps({"classification": branch, "reason": "Keyword match"}))
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in prompt_classifier: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
```

- [x] **Step 4: Update `stop_verifier.py`**
Add missing imports and remove nested `try/except` in `src/harness/templates/boilerplate/hooks/stop_verifier.py`. *(Note: Ensure you preserve existing imports and helper functions when updating `main()`)*:
```python
import sys
import json
import os
import subprocess
from pathlib import Path
from hook_common import resolve_project_root
# Implementer: Preserve any other existing imports/functions here!

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        project_root = resolve_project_root(input_data)
        plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent)).resolve()
        script_path = plugin_root / "scripts" / "verify_contract.py"
        
        if not script_path.exists():
            sys.exit(0)
            
        # Inner try block removed. Subprocess errors will trigger the global exception block.
        process = subprocess.run(
            [sys.executable, str(script_path), str(project_root)],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        if process.returncode != 0:
            out = process.stdout + "\n" + process.stderr
            # Use logic similar to extract_stacktrace.py to grab the relevant failure context
            # rather than naively taking the first 100 lines.
            print(f"Verification failed:\n{out[-2000:]}", file=sys.stderr) # Fallback simple truncation for safety, but implementer should refine.
            sys.exit(2)
                
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in stop_verifier: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
```

### Task 3: Add Automated Test Coverage for Circuit Breaker

**Files:**
- Modify: `tests/hooks/test_claude_hooks.py`

- [x] **Step 1: Add Circuit Breaker Tests**
Inject 3 consecutive failures to test the circuit breaker correctly terminates execution.
```python
import tempfile
import json
from pathlib import Path

def test_circuit_breaker_trips_pre_tool_guard():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "campaign_state.json"
        
        # Setup mock state with 3 failures
        state_file.write_text(json.dumps({"consecutive_tool_failures": 3}))
        
        input_data = {
            "tool_name": "Task",
            "tool_input": {"prompt": "do something"}
        }
        
        # Run pre_tool_guard
        res = run_hook("pre_tool_guard.py", input_data, tmp_path)
        
        # Assert circuit breaker tripped
        assert res["returncode"] == 2
        assert "Circuit breaker tripped" in res["stderr"]
        
        # Verify it reset the counter
        updated_state = json.loads(state_file.read_text())
        assert updated_state.get("consecutive_tool_failures") == 0

def test_circuit_breaker_trips_post_tool_observer():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "campaign_state.json"
        
        # Setup mock state with 2 failures, trigger a 3rd
        state_file.write_text(json.dumps({"consecutive_tool_failures": 2}))
        
        input_data = {
            "hook_event_name": "PostToolUseFailure",
            "error": "Some tool error"
        }
        
        # Run post_tool_observer
        res = run_hook("post_tool_observer.py", input_data, tmp_path)
        
        # Assert circuit breaker tripped
        assert res["returncode"] == 2
        assert "Circuit breaker tripped" in res["stderr"]
```
*(Ensure the test suite invokes these checks explicitly using existing framework utilities like `run_hook`)*

## Verification
- Run test suite: `pytest tests/hooks/test_claude_hooks.py`
- Verify that `test_circuit_breaker_trips_pre_tool_guard` and `test_circuit_breaker_trips_post_tool_observer` both pass.
- Trigger a deliberate internal crash in one of the hooks and verify it returns `exit 2`.exit 2`.