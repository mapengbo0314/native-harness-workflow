# Harness Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the "Ask First" bug routing protocol in the Orchestrator and create a polyglot stack trace extraction script for error processing.

**Architecture:** 
1.  Add a Python script (`extract_stacktrace.py`) to the boilerplate agent scripts directory. This script uses simple heuristics to locate the core error and surrounding lines in a log file.
2.  Modify the Orchestrator's `dispatch_rules.md` to introduce the `ask_user` gate for bug routing and update relevant skill prompts to mandate the use of the extraction script.

**Tech Stack:** Python, Markdown (Agent System Prompts)

---

### Task 1: Create the Stack Trace Extractor Script

**Files:**
- Create: `boilerplate-agent/scripts/extract_stacktrace.py`
- Create: `tests/unit/test_extract_stacktrace.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_extract_stacktrace.py`:
```python
import os
import subprocess
import tempfile
import sys

def test_python_traceback_extraction():
    # Setup dummy log file
    log_content = """
Some noisy pytest setup logs
...
...
Traceback (most recent call last):
  File "/usr/lib/python3.10/unittest/case.py", line 59, in testPartExecutor
    yield
  File "/usr/lib/python3.10/unittest/case.py", line 591, in run
    self._callTestMethod(testMethod)
  File "/workspace/my_project/tests/test_feature.py", line 42, in test_broken_thing
    assert calculate(5) == 10
AssertionError: assert 5 == 10
More noise...
"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
        f.write(log_content)
        log_path = f.name

    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'boilerplate-agent', 'scripts', 'extract_stacktrace.py')
    
    try:
        result = subprocess.run([sys.executable, script_path, log_path], capture_output=True, text=True)
        output = result.stdout
        
        assert "AssertionError: assert 5 == 10" in output
        assert "/workspace/my_project/tests/test_feature.py" in output
        assert "line 42" in output
        assert "testPartExecutor" not in output # Should ignore stdlib frames if heuristic works well, but at minimum should have the core error.
    finally:
        os.remove(log_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_extract_stacktrace.py -v`
Expected: FAIL (File not found or module execution fails)

- [ ] **Step 3: Write minimal implementation**

Create `boilerplate-agent/scripts/extract_stacktrace.py`:
```python
#!/usr/bin/env python3
import sys
import re

def extract_trace(log_content):
    lines = log_content.splitlines()
    extracted = []
    in_trace = False
    
    # Simple heuristic for Python and generic Node errors
    for idx, line in enumerate(lines):
        if "Traceback (most recent call last):" in line or line.strip().startswith("Error:"):
            in_trace = True
            # Capture some lines before the trace for context if possible
            start_idx = max(0, idx - 2)
            extracted.extend(lines[start_idx:idx])
            
        if in_trace:
            extracted.append(line)
            # End of trace heuristic (empty line or start of new unrelated log block)
            # This is a very basic heuristic; a real one would be more robust.
            if not line.strip() and len(extracted) > 5:
                # Capture a few lines after
                end_idx = min(len(lines), idx + 3)
                extracted.extend(lines[idx+1:end_idx])
                break
                
    if not extracted:
        # Fallback: just return the last 30 lines
        return "\n".join(lines[-30:])
        
    return "\n".join(extracted)

def main():
    if len(sys.argv) < 2:
        print("Usage: extract_stacktrace.py <logfile>")
        sys.exit(1)
        
    log_file = sys.argv[1]
    try:
        with open(log_file, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {log_file}: {e}")
        sys.exit(1)
        
    result = extract_trace(content)
    print("=== EXTRACTED STACK TRACE ===")
    print(result)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_extract_stacktrace.py -v`
Expected: PASS

- [ ] **Step 5: Make script executable and Commit**

```bash
chmod +x boilerplate-agent/scripts/extract_stacktrace.py
git add boilerplate-agent/scripts/extract_stacktrace.py tests/unit/test_extract_stacktrace.py
git commit -m "feat(hook): add intelligent stacktrace extraction script"
```

### Task 2: Update Orchestrator Dispatch Rules

**Files:**
- Modify: `boilerplate-agent/rules/dispatch_rules.md`

- [ ] **Step 1: Update the Complexity Assessment policy**

Edit `boilerplate-agent/rules/dispatch_rules.md`. Find `<tool_delegation_policy>` and replace the `Complexity Assessment & Routing (CRITICAL):` section with the following text:

```markdown
**Complexity Assessment & Bug Routing (CRITICAL):**
Before routing, you MUST assess the user's request to save tokens and time:
- **Low Complexity (Auto-Fast Path)**: If the prompt explicitly provides the exact file/line to fix, or explicitly requests a "quick fix" for a minor tweak, you MUST bypass the heavy Superpower workflows (no `@planner`, no `brainstorming`). Delegate directly to the `@implementer` and then `@reviewer`.
- **The "Ask First" Gate (Bug Reports)**: If the prompt is a pasted log, stack trace, or a vague failure report, you MUST use the `ask_user` tool before proceeding:
   - **Question:** "Should I route this as a quick, localized fix, or run a deep architectural diagnosis?"
   - **Options:** `["Quick Fix (Fast Path)", "Deep Diagnosis (Standard Path)"]`
   - **Fallback:** If `ask_user` is unavailable or the user tells you to decide, default to the **Fast Path** (`@implementer`).
- **High Complexity (Standard Path)**: Multi-file features, architectural changes, deep diagnosis, or step-by-step designs. Enforce the full Superpower workflow. If the task is a bug diagnosis, you MUST route to the `@architect` and explicitly instruct them to activate the `diagnose` skill. For features, follow (`brainstorming` -> `@planner` -> `@implementer` -> `@reviewer` -> `@verifier`).
- **Escalation Loop**: If the `@implementer` fails to resolve a bug on the Fast Path, you must catch the failure and immediately escalate to the **Standard Path** (`@architect` -> `@planner`). When escalating to the `@architect`, you MUST instruct them to activate the `diagnose` skill before proceeding.
```

- [ ] **Step 2: Commit**

```bash
git add boilerplate-agent/rules/dispatch_rules.md
git commit -m "feat(router): implement Ask First bug routing protocol"
```

### Task 3: Mandate Stack Trace Extractor Usage

**Files:**
- Modify: `boilerplate-agent/skills/diagnose/SKILL.md`
- Modify: `boilerplate-agent/agents/implementer.md`

- [ ] **Step 1: Update the diagnose skill instructions**

Edit `boilerplate-agent/skills/diagnose/SKILL.md`. Find the "Diagnose Instructions" or "Checklist" section and add the following step at the beginning of the log analysis phase:

```markdown
- **Stack Trace Extraction (MANDATORY)**: When analyzing test failures, build errors, or large log files, you MUST NOT use `read_file` to read the entire raw file. You MUST run `run_shell_command("python {{HARNESS_DIR}}/scripts/extract_stacktrace.py <logfile>")` first to extract the exact error payload and concise context.
```

- [ ] **Step 2: Update the Implementer agent prompt**

Edit `boilerplate-agent/agents/implementer.md`. Find the "Implementer Constraints" section and append the following bullet point:

```markdown
- **Stack Trace Extraction**: When a test fails or you need to read a log file, do NOT read the entire raw file. You MUST run `run_shell_command("python {{HARNESS_DIR}}/scripts/extract_stacktrace.py <logfile>")` to get the condensed error context.
```

- [ ] **Step 3: Commit**

```bash
git add boilerplate-agent/skills/diagnose/SKILL.md boilerplate-agent/agents/implementer.md
git commit -m "feat(hook): mandate stacktrace extractor usage in diagnose and implementer"
```