# Autonomous Verification Engine Implementation Plan (Phase 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement autonomous recovery and self-healing loops in the Orchestrator when verification fails.

**Architecture:** 
1.  **Failure Analysis:** Update the `@verifier` to provide structured failure metadata (e.g., "COMPILATION_ERROR", "TEST_FAILURE").
2.  **Rerouting Logic:** Update the Orchestrator's `using-harness-superpowers` flow to intercept `@verifier` failures.
3.  **3-Strike Gate:** Implement a counter that triggers a high-level `[RECOVERY_FLOW]` after 3 consecutive failures, forcing the Orchestrator to re-plan or ask for human help.

**Tech Stack:** Python (Harness Core), Markdown (Agent Mandates/Skills), Jinja2 (Templates).

---

### Task 1: Structured Failure Reporting in Verifier

**Files:**
- Modify: `src/harness/templates/boilerplate/agents/verifier.md`
- Modify: `src/harness/templates/boilerplate/skills/verification-before-completion/SKILL.md`

- [ ] **Step 1: Update Verifier Mandate to provide JSON metadata**
Add a requirement for the Verifier to include a hidden XML/JSON block in `QA_REPORT.md` with failure categories.

```markdown
### Reporting Format:
- Always include a `QA_METADATA` block at the end of `QA_REPORT.md`:
<QA_METADATA>
{
  "status": "FAIL",
  "category": "TEST_FAILURE | COMPILATION_ERROR | TIMEOUT",
  "affected_files": ["path/to/file.py"],
  "failure_summary": "Short description"
}
</QA_METADATA>
```

- [ ] **Step 2: Update `verification-before-completion` to parse metadata**
Update the skill to extract this metadata and present it to the Orchestrator in a machine-readable way.

---

### Task 2: Orchestrator Autonomous Recovery Flow

**Files:**
- Modify: `src/harness/templates/boilerplate/orchestrator.md`

- [ ] **Step 1: Implement the 3-Strike Rule**
Inject a state-tracking mandate into the Orchestrator boilerplate.

```markdown
### AUTONOMOUS RECOVERY (3-STRIKE RULE):
- Maintain a `verification_attempts` counter in your private memory.
- If `@verifier` returns a `FAIL`:
    1. **Attempt 1-2:** Analyze the `QA_METADATA`. Automatically delegate a fix to `@implementer` (if code error) or `@planner` (if design error).
    2. **Attempt 3:** You MUST enter `[RECOVERY_FLOW]`. Halt autonomous execution and use `ask_user` to provide a deep analysis of why the fix is failing and request a strategic pivot.
```

- [ ] **Step 2: Update the Decision Matrix**
Add a new Branch for "Verification Remediation".

---

### Task 3: State Tracking in Hook Logic (The Safety Net)

**Files:**
- Modify: `src/harness/plugin_generator.py` (hook_validator.py template)

- [ ] **Step 1: Implement Server-Side Failure Tracking**
Update the Python hook logic to track `consecutive_verification_failures` in the local `.harness/state.json`.

```python
# src/harness/templates/hooks/post_tool_monitor.py
if "QA_REPORT.md" in modified_files:
    report = read_file("artifacts/qa_report.md")
    if "STATUS: FAIL" in report:
        state["consecutive_failures"] += 1
        if state["consecutive_failures"] >= 3:
            print("[CRITICAL] 3 consecutive verification failures detected. Locking autonomous mode.")
            state["locked"] = True
```

- [ ] **Step 2: Verify with a Unit Test**
Create `tests/unit/test_autonomous_recovery.py` to simulate 3 failures and verify the lock.

---

### Task 4: Final Integration & Regression Test

**Files:**
- Create: `tests/e2e/test_autonomous_recovery_loop.py`

- [ ] **Step 1: Create an E2E test that simulates a 'Hard Bug'**
1. Mint a harness.
2. Introduce a bug that requires multiple steps to fix.
3. Verify that the Orchestrator attempts the fix twice and triggers recovery on the third.

- [ ] **Step 2: Commit**
```bash
git add src/harness/
git commit -m "feat: implement phase 2 autonomous recovery engine"
```
