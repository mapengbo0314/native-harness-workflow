# Circuit Breaker and Global Fail-Safes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce strict fail-safes across all hook templates to ensure any crash blocks the agent (`exit 2`), and implement a circuit breaker that hard-stops the agent after 3 consecutive tool failures.

**Architecture:** We wrap the `main()` function execution of all hook scripts in a `try...except Exception` block that prints to stderr and calls `sys.exit(2)`. For the circuit breaker, `post_tool_observer.py` already tracks `consecutive_tool_failures`; we will modify `pre_tool_guard.py` and `post_tool_observer.py` to trigger the circuit breaker (`exit 2`) when this count reaches 3.

**Tech Stack:** Python, JSON

---

### Task 1: Add Circuit Breaker to `post_tool_observer.py` and `pre_tool_guard.py`

**Files:**
- Modify: `src/harness/templates/boilerplate/hooks/post_tool_observer.py`
- Modify: `src/harness/templates/boilerplate/hooks/pre_tool_guard.py`

- [ ] **Step 1: Import `read_json` and add circuit breaker check to `post_tool_observer.py`**

Modify `src/harness/templates/boilerplate/hooks/post_tool_observer.py` to import `read_json` and check the failure count:

```python
import sys
import json
from hook_common import resolve_state_path, update_state, read_json

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(0)
            
        has_error = input_data.get("error") is not None or input_data.get("type") == "PostToolUseFailure"
        
        state_path = resolve_state_path(input_data)
        
        def modifier(s):
            if "consecutive_tool_failures" not in s:
                s["consecutive_tool_failures"] = 0
                
            if has_error:
                s["consecutive_tool_failures"] += 1
            else:
                s["consecutive_tool_failures"] = 0
                
        update_state(state_path, modifier)
        
        # Check circuit breaker
        state = read_json(state_path)
        if state.get("consecutive_tool_failures", 0) >= 3:
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

- [ ] **Step 2: Add circuit breaker check to `pre_tool_guard.py` and wrap in global try/except**

Replace the `main()` function in `src/harness/templates/boilerplate/hooks/pre_tool_guard.py` with:

```python
def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(0)

        tool_name = input_data.get("tool_name") or input_data.get("toolName", "")
        tool_input = input_data.get("tool_input") or input_data.get("toolInput", {})
        
        if tool_name in ["Write", "Edit", "MultiEdit", "Bash", "run_shell_command", "write_file", "replace"]:
            for candidate in _candidate_paths(tool_input):
                if is_protected_path(candidate, input_data):
                    print(f"Error: Access to protected path '{candidate}' is blocked.", file=sys.stderr)
                    sys.exit(2)
                    
        # Check Branch D planner/verifier escalation & Circuit Breaker
        state_path = resolve_state_path(input_data)
        state = read_json(state_path)
        
        if state.get("consecutive_tool_failures", 0) >= 3:
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

- [ ] **Step 1: Wrap `main()` in `config_change_guard.py`**

Replace `main()` in `src/harness/templates/boilerplate/hooks/config_change_guard.py`:

```python
def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(0)
            
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

- [ ] **Step 2: Wrap `main()` in `precompact_handoff.py`**

Replace `main()` in `src/harness/templates/boilerplate/hooks/precompact_handoff.py`:

```python
def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(0)
            
        state_path = resolve_state_path(input_data)
        state = read_json(state_path)
        
        project_root = resolve_project_root(input_data)
        handoff_path = project_root / "HANDOFF.md"
        
        goal = state.get("goal", "Unknown Goal")
        progress = state.get("progress", "Unknown Progress")
        next_steps = state.get("next_steps", "Unknown Next Steps")
        
        content = f"# HANDOFF\n\n## Goal\n{goal}\n\n## Progress\n{progress}\n\n## Next Steps\n{next_steps}\n"
        
        try:
            with open(handoff_path, "w") as f:
                f.write(content)
                
            def modifier(s):
                s["handoff_written"] = True
                
            update_state(state_path, modifier)
            
        except Exception as e:
            print(f"Failed to write HANDOFF.md: {e}", file=sys.stderr)
            sys.exit(2)
            
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in precompact_handoff: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Wrap `main()` in `prompt_classifier.py`**

Replace `main()` in `src/harness/templates/boilerplate/hooks/prompt_classifier.py`:

```python
def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(0)
            
        prompt = input_data.get("prompt", "")
        branch = classify(prompt)
        
        def modifier(state):
            state["current_branch"] = branch
            state["last_prompt"] = prompt[:100]
            
        try:
            state_path = resolve_state_path(input_data)
            update_state(state_path, modifier)
        except Exception as e:
            print(f"Error updating state: {e}", file=sys.stderr)
            
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

- [ ] **Step 4: Wrap `main()` in `stop_verifier.py`**

Replace `main()` in `src/harness/templates/boilerplate/hooks/stop_verifier.py`:

```python
def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(0)
            
        project_root = resolve_project_root(input_data)
        plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent)).resolve()
        script_path = plugin_root / "scripts" / "verify_contract.py"
        
        if not script_path.exists():
            sys.exit(0)
            
        try:
            process = subprocess.run(
                [sys.executable, str(script_path), str(project_root)],
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            if process.returncode != 0:
                out = process.stdout + "\n" + process.stderr
                lines = out.splitlines()[:100]
                summary = "\n".join(lines)[:10000]
                print(f"Verification failed:\n{summary}", file=sys.stderr)
                sys.exit(2)
                
        except Exception as e:
            print(f"Verification script execution error: {e}", file=sys.stderr)
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

- [ ] **Step 5: Run tests to verify the failsafe**

Create a quick sanity check script or test one of the hooks manually with a deliberate failure:
```bash
echo '{invalid json}' | python3 src/harness/templates/boilerplate/hooks/pre_tool_guard.py
# Should exit 0 since JSON Decode errors are ignored safely

echo '{"tool_name": "Task"}' | python3 src/harness/templates/boilerplate/hooks/pre_tool_guard.py
# Should exit cleanly or with specific block, depending on state
```