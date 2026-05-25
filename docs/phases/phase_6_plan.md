# Phase 6: Task Tracker and Handoff Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move task progress out of prose (`task_progress.md`) and into deterministic state within `campaign_state.json`.

**Architecture:** We will introduce two CLI scripts to the boilerplate templates. `task_tracker.py` modifies the state using atomic operations from `hook_common.py`. `harness_resume.py` reads the state and produces a capped, deterministic markdown summary suitable for context injection.

**Tech Stack:** Python 3, `argparse`, existing JSON state management in `hook_common.py`.

---

## Context
- The Harness Generator copies `src/harness/templates/boilerplate/scripts/` to the target plugin.
- State is managed via `src/harness/templates/boilerplate/state/campaign_state.json` and manipulated via `hooks/hook_common.py`.
- We need to expose a determinist way to read/write task progress without bloat.

## Design Doc

### Problem Statement
Task progress is currently maintained in prose (`task_progress.md`), which is hard to parse deterministically, prone to drift, and difficult for agents to query efficiently without consuming excessive context window.

### Proposed Design
Introduce `task_tracker.py` and `harness_resume.py` into the boilerplate templates.
- **`campaign_state.schema.json` & `campaign_state.json`**: Will be extended to include a top-level `"tasks"` object representing the active goal and its steps.
- **`task_tracker.py`**: A CLI script in `scripts/` that allows updating tasks via commands: `--set-goal`, `--add-step`, `--complete-step`. It relies on `hook_common.update_state`.
- **`harness_resume.py`**: A CLI script that safely reads `campaign_state.json` and outputs a concise Markdown summary (capped at 1000 characters).

### Alternatives
- *Regex parsing `task_progress.md`:* Brittle and fails when agents slightly alter markdown structure.
- *SQLite database:* Overcomplicates the simple JSON file contract that `hook_common.py` already standardizes.

### Sphinch Marks
- [ ] Schema allows a `tasks` object with `current_goal` (string) and `steps` (array).
- [ ] `task_tracker.py` updates the `campaign_state.json` accurately.
- [ ] `harness_resume.py` prints a capped text summary.
- [ ] `hook_common.update_state` is used for concurrency safety.

## Plan

### Task 1: Update State Schema and Initial State

**Files:**
- Modify: `src/harness/templates/boilerplate/contracts/campaign_state.schema.json`
- Modify: `src/harness/templates/boilerplate/state/campaign_state.json`

- [ ] **Step 1: Extend Schema with Tasks Block**

In `src/harness/templates/boilerplate/contracts/campaign_state.schema.json`, add the `tasks` property to the `properties` object (don't make it required so older versions don't break):

```json
    "tasks": {
      "type": "object",
      "properties": {
        "current_goal": { "type": "string" },
        "steps": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": { "type": "string" },
              "status": { "type": "string", "enum": ["pending", "completed"] }
            },
            "required": ["name", "status"]
          }
        }
      }
    }
```

- [ ] **Step 2: Add Tasks Block to Default State**

In `src/harness/templates/boilerplate/state/campaign_state.json`, add an empty tasks object:

```json
{
  "metadata": {},
  "tasks": {
    "current_goal": "",
    "steps": []
  },
  "events": []
}
```

- [ ] **Step 3: Commit**

```bash
git add src/harness/templates/boilerplate/contracts/campaign_state.schema.json src/harness/templates/boilerplate/state/campaign_state.json
git commit -m "feat: add tasks block to campaign state schema"
```

### Task 2: Implement Task Tracker

**Files:**
- Create: `src/harness/templates/boilerplate/scripts/task_tracker.py`
- Create: `tests/unit/test_task_tracker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_task_tracker.py
import json
import subprocess
import sys
from pathlib import Path

def test_task_tracker(tmp_path):
    # Setup mock plugin environment
    plugin_dir = tmp_path / ".claude" / "plugin-generated"
    plugin_dir.mkdir(parents=True)
    
    state_dir = plugin_dir / "state"
    state_dir.mkdir()
    state_path = state_dir / "campaign_state.json"
    
    # Initialize state
    with open(state_path, "w") as f:
        json.dump({"tasks": {"current_goal": "", "steps": []}}, f)

    script_path = Path("src/harness/templates/boilerplate/scripts/task_tracker.py")
    
    # Set goal
    env = {"CLAUDE_PLUGIN_ROOT": str(plugin_dir)}
    res = subprocess.run(
        [sys.executable, str(script_path), "--set-goal", "Finish phase 6"],
        env=env, capture_output=True, text=True
    )
    assert res.returncode == 0
    
    # Add step
    res = subprocess.run(
        [sys.executable, str(script_path), "--add-step", "Write tests"],
        env=env, capture_output=True, text=True
    )
    assert res.returncode == 0
    
    # Complete step
    res = subprocess.run(
        [sys.executable, str(script_path), "--complete-step", "Write tests"],
        env=env, capture_output=True, text=True
    )
    assert res.returncode == 0
    
    with open(state_path, "r") as f:
        data = json.load(f)
    
    assert data["tasks"]["current_goal"] == "Finish phase 6"
    assert len(data["tasks"]["steps"]) == 1
    assert data["tasks"]["steps"][0]["name"] == "Write tests"
    assert data["tasks"]["steps"][0]["status"] == "completed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_task_tracker.py -v`
Expected: FAIL due to missing script `src/harness/templates/boilerplate/scripts/task_tracker.py`

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/templates/boilerplate/scripts/task_tracker.py
import argparse
import sys
from pathlib import Path

# Add the hooks directory to sys.path so we can import hook_common
# scripts/ is a sibling to hooks/ in the generated plugin
plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(plugin_root / "hooks"))

from hook_common import resolve_state_path, update_state

def main():
    parser = argparse.ArgumentParser(description="Deterministic task tracking.")
    parser.add_argument("--set-goal", type=str, help="Set the current goal")
    parser.add_argument("--add-step", type=str, help="Add a new step")
    parser.add_argument("--complete-step", type=str, help="Mark a step as completed")
    
    args = parser.parse_args()
    state_path = resolve_state_path()
    
    def modifier(data: dict):
        if "tasks" not in data:
            data["tasks"] = {"current_goal": "", "steps": []}
            
        if args.set_goal:
            data["tasks"]["current_goal"] = args.set_goal
        
        if args.add_step:
            # Prevent duplicates
            if not any(s["name"] == args.add_step for s in data["tasks"]["steps"]):
                data["tasks"]["steps"].append({"name": args.add_step, "status": "pending"})
                
        if args.complete_step:
            for step in data["tasks"]["steps"]:
                if step["name"] == args.complete_step:
                    step["status"] = "completed"
                    break

    update_state(state_path, modifier)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_task_tracker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/templates/boilerplate/scripts/task_tracker.py tests/unit/test_task_tracker.py
git commit -m "feat: add task tracker script"
```

### Task 3: Implement Harness Resume

**Files:**
- Create: `src/harness/templates/boilerplate/scripts/harness_resume.py`
- Create: `tests/unit/test_harness_resume.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_harness_resume.py
import json
import subprocess
import sys
from pathlib import Path

def test_harness_resume(tmp_path):
    plugin_dir = tmp_path / ".claude" / "plugin-generated"
    plugin_dir.mkdir(parents=True)
    state_dir = plugin_dir / "state"
    state_dir.mkdir()
    state_path = state_dir / "campaign_state.json"
    
    with open(state_path, "w") as f:
        json.dump({
            "tasks": {
                "current_goal": "Deploy app",
                "steps": [
                    {"name": "Build", "status": "completed"},
                    {"name": "Test", "status": "pending"}
                ]
            }
        }, f)

    script_path = Path("src/harness/templates/boilerplate/scripts/harness_resume.py")
    env = {"CLAUDE_PLUGIN_ROOT": str(plugin_dir)}
    res = subprocess.run(
        [sys.executable, str(script_path)],
        env=env, capture_output=True, text=True
    )
    
    assert res.returncode == 0
    out = res.stdout
    assert "Current Goal: Deploy app" in out
    assert "[x] Build" in out
    assert "[ ] Test" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_harness_resume.py -v`
Expected: FAIL due to missing script.

- [ ] **Step 3: Write minimal implementation**

```python
# src/harness/templates/boilerplate/scripts/harness_resume.py
import sys
from pathlib import Path

plugin_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(plugin_root / "hooks"))

from hook_common import resolve_state_path, read_json

def main():
    state_path = resolve_state_path()
    state = read_json(state_path)
    
    tasks = state.get("tasks", {})
    goal = tasks.get("current_goal", "No active goal")
    steps = tasks.get("steps", [])
    
    output = []
    output.append(f"### Current Goal: {goal}")
    output.append("### Steps:")
    
    if not steps:
        output.append("No steps defined.")
    else:
        for step in steps:
            mark = "x" if step.get("status") == "completed" else " "
            output.append(f"- [{mark}] {step.get('name')}")
            
    # Combine and cap summary at 1000 characters
    summary = "\n".join(output)
    if len(summary) > 1000:
        summary = summary[:997] + "..."
        
    print(summary)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_harness_resume.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/templates/boilerplate/scripts/harness_resume.py tests/unit/test_harness_resume.py
git commit -m "feat: add harness resume script"
```