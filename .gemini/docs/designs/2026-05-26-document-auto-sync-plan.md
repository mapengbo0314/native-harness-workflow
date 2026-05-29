# Document State Auto-Sync & Failure Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate document lifecycle management by writing a sync script that moves markdown files between directories based on `manifest.json` state, and removing manual file-movement instructions from agent templates.

**Architecture:** A new python script `sync_manifest_state.py` acts as a git hook (triggered via `PreCommit` in `hooks.json`). It reads the central `manifest.json` and automatically executes `git mv` to ensure physical files align with their JSON state.

**Tech Stack:** Python, Bash, Markdown

---

### Task 1: Create `sync_manifest_state.py` Script

**Files:**
- Create: `src/harness/templates/boilerplate/scripts/sync_manifest_state.py`
- Test: `tests/hooks/test_sync_manifest_state.py`

- [ ] **Step 1: Write the failing test**

```python
import os
import json
import shutil
import pytest
import subprocess
from pathlib import Path

def test_sync_manifest_moves_files(tmp_path):
    # Setup mock git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    
    docs_dir = tmp_path / "docs"
    for d in ["proposed", "inprogress", "completed", "reference"]:
        (docs_dir / d).mkdir(parents=True)
        
    manifest_path = docs_dir / "manifest.json"
    manifest_path.write_text(json.dumps({
        "docs": [
            {"name": "test-doc", "state": "inprogress", "progress_doc_path": "inprogress/test-doc-progress.md"}
        ]
    }))
    
    # Create the files in the WRONG location (e.g. still in proposed)
    proposed_file = docs_dir / "proposed" / "test-doc.md"
    proposed_file.write_text("# Test Doc")
    subprocess.run(["git", "add", ".gemini/docs/designs/test-doc.md"], cwd=tmp_path, check=True)
    
    progress_file = docs_dir / "inprogress" / "test-doc-progress.md"
    progress_file.write_text("# Progress")
    subprocess.run(["git", "add", ".gemini/docs/designs/test-doc-progress.md"], cwd=tmp_path, check=True)
    
    # Run the script
    script_path = Path("src/harness/templates/boilerplate/scripts/sync_manifest_state.py").resolve()
    result = subprocess.run(["python3", str(script_path)], cwd=tmp_path, capture_output=True, text=True)
    
    # Verify file moved
    assert not proposed_file.exists()
    assert (docs_dir / "inprogress" / "test-doc.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/hooks/test_sync_manifest_state.py`
Expected: FAIL with "No module named" or file not found.

- [ ] **Step 3: Write minimal implementation**

```python
import os
import json
import subprocess
from pathlib import Path

def main():
    project_root = Path.cwd()
    docs_dir = project_root / "docs"
    manifest_path = docs_dir / "manifest.json"
    
    if not manifest_path.exists():
        return
        
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except Exception:
        return
        
    for doc in manifest.get("docs", []):
        name = doc.get("name")
        state = doc.get("state")
        if not name or not state:
            continue
            
        target_dir = docs_dir / state
        expected_path = target_dir / f"{name}.md"
        
        # If the file is already in the right place, skip
        if expected_path.exists():
            continue
            
        # Look for it in other state directories
        for other_state in ["proposed", "inprogress", "completed", "reference"]:
            if other_state == state:
                continue
            
            wrong_path = docs_dir / other_state / f"{name}.md"
            if wrong_path.exists():
                print(f"[DocSync] Moving {wrong_path.relative_to(project_root)} to {expected_path.relative_to(project_root)}")
                # Use git mv to preserve history if tracked
                try:
                    subprocess.run(["git", "mv", str(wrong_path), str(expected_path)], check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    # Fallback to normal mv if not tracked by git
                    wrong_path.rename(expected_path)
                    
        # Handle progress docs for 'completed' state
        progress_path = doc.get("progress_doc_path")
        if state == "completed" and progress_path and progress_path.startswith("inprogress/"):
            # Progress doc needs to move to reference
            wrong_prog_path = docs_dir / progress_path
            new_prog_rel = progress_path.replace("inprogress/", "reference/", 1)
            expected_prog_path = docs_dir / new_prog_rel
            
            if wrong_prog_path.exists():
                print(f"[DocSync] Archiving progress doc {wrong_prog_path.relative_to(project_root)} to {expected_prog_path.relative_to(project_root)}")
                try:
                    subprocess.run(["git", "mv", str(wrong_prog_path), str(expected_prog_path)], check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    wrong_prog_path.rename(expected_prog_path)
                    
                # We do NOT rewrite the manifest progress_doc_path here to avoid infinite loops with git commits,
                # the prompt templates will instruct agents to update the manifest path.

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/hooks/test_sync_manifest_state.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/templates/boilerplate/scripts/sync_manifest_state.py tests/hooks/test_sync_manifest_state.py
git commit -m "feat(hooks): add manifest state synchronization script"
```

---

### Task 2: Wire up `hooks.json`

**Files:**
- Modify: `src/harness/templates/boilerplate/hooks/hooks.json`

- [ ] **Step 1: Write the implementation**

Update `src/harness/templates/boilerplate/hooks/hooks.json` to add the `PreCommit` trigger for the sync script. 

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "filters": [
          {"type": "exact_match", "path": "hook_event_name", "value": "UserPromptSubmit"}
        ],
        "hooks": [
          {"command": "python3 ${HARNESS_PLUGIN_ROOT}/hooks/prompt_classifier.py"}
        ]
      }
    ],
    "PreCommit": [
      {
        "filters": [],
        "hooks": [
          {"command": "${HARNESS_PLUGIN_ROOT}/hooks/doc-manifest-validator.sh"},
          {"command": "python3 ${HARNESS_PLUGIN_ROOT}/scripts/sync_manifest_state.py"}
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add src/harness/templates/boilerplate/hooks/hooks.json
git commit -m "feat(hooks): wire sync_manifest_state.py to PreCommit in boilerplate"
```

---

### Task 3: Refactor Boilerplate Agent Templates

**Files:**
- Modify: `src/harness/templates/boilerplate/agents/planner.md`
- Modify: `src/harness/templates/boilerplate/agents/implementer.md`
- Modify: `src/harness/templates/boilerplate/agents/reviewer.md`
- Modify: `src/harness/templates/boilerplate/agents/verifier.md`
- Modify: `src/harness/templates/boilerplate/AGENTS.md`

- [ ] **Step 1: Write the implementation**

In `src/harness/templates/boilerplate/agents/planner.md`:
Find:
`- **Execution Boundaries**: A plan does not authorize implementation. You MUST write your final design to .gemini/docs/designs/implementation_plan.md and then halt.`
Replace with:
`- **Execution Boundaries**: A plan does not authorize implementation. You MUST create the design in .gemini/docs/designs/ and add it to .gemini/docs/manifest.json with state=proposed, then halt.`

In `src/harness/templates/boilerplate/agents/implementer.md`:
Find:
`1. Move the design from .gemini/docs/designs/{design_name}.md to .gemini/docs/designs/{design_name}.md.`
`2. Create a **progress document** at .gemini/docs/designs/{design_name}-progress.md.`
`3. Update .gemini/docs/manifest.json:`
Replace with:
`1. Update .gemini/docs/manifest.json: change state from proposed to inprogress.`
`2. Create a **progress document** at .gemini/docs/designs/{design_name}-progress.md.`
*(Remove instructions telling them to manually move the design doc).*

Find:
`- Do not attempt architecture or planning redesigns. If execution fails fundamentally, write findings to .gemini/docs/reference/{design_doc}_failure_report.md and halt.`
Replace with:
`- Do not attempt architecture or planning redesigns. If execution fails fundamentally, append findings, stack traces, and required fixes to the 'Current Blockers' section of .gemini/docs/designs/{design_name}-progress.md and halt.`

In `src/harness/templates/boilerplate/agents/reviewer.md` & `verifier.md`:
Find:
`- Validate the progress doc and move state to completed in .gemini/docs/manifest.json on PASS, or write failure reports to .gemini/docs/reference/ on FAIL.`
Replace with:
`- Validate the progress doc and change state to completed in .gemini/docs/manifest.json on PASS. On FAIL, append failure findings and required fixes to the 'Current Blockers' section of .gemini/docs/designs/{design_name}-progress.md.`

In `src/harness/templates/boilerplate/AGENTS.md`:
Update the mandates to match the above changes (remove manual file moves, enforce appending failures to progress doc instead of failure_report.md).

- [ ] **Step 2: Commit**

```bash
git add src/harness/templates/boilerplate/agents/*.md src/harness/templates/boilerplate/AGENTS.md
git commit -m "refactor(templates): remove manual file moves and integrate unified failure reporting"
```

---

### Task 4: Refactor Active Session Agent Templates

**Files:**
- Modify: `.gemini/agents/planner.md`
- Modify: `.gemini/agents/implementer.md`
- Modify: `.gemini/agents/reviewer.md`
- Modify: `.gemini/agents/verifier.md`
- Modify: `.gemini/AGENTS.md`

- [ ] **Step 1: Write the implementation**

Apply the exact same textual replacements as Task 3, but to the active `.gemini/` files. This ensures the current session uses the new rules immediately.

- [ ] **Step 2: Commit**

```bash
git add .gemini/agents/*.md .gemini/AGENTS.md
git commit -m "refactor(agents): sync active session templates with new auto-sync and failure reporting mandates"
```

---

### Task 5: Update `docs/README.md` System Guide

**Files:**
- Modify: `src/harness/templates/boilerplate/docs/README.md`

- [ ] **Step 1: Write the implementation**

In `src/harness/templates/boilerplate/docs/README.md`:

Under `## For Implementer Agents`, change:
`1. Move the design from .gemini/docs/designs/{design_name}.md to .gemini/docs/designs/{design_name}.md.`
To:
`1. Create a **progress document** at .gemini/docs/designs/{design_name}-progress.md.`
`2. Update .gemini/docs/manifest.json to change state from proposed to inprogress. (The system will automatically move the design doc via a pre-commit hook).`

Under `## For Verifier Agents` -> `### On PASS`:
Remove `1. Move design from .gemini/docs/designs/{design_name}.md to docs/completed/{design_name}.md.`
Add note that system handles the moves.

Under `### On FAIL`:
Explicitly state: `If verification fails, append findings and required fixes to the "Current Blockers" section in the progress doc and return to Implementer. Do not create separate failure report files.`

- [ ] **Step 2: Commit**

```bash
git add src/harness/templates/boilerplate/docs/README.md
git commit -m "docs(boilerplate): update document state system README to reflect auto-sync architecture"
```