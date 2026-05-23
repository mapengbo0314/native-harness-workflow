# Deterministic Verification & High-Fidelity Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Agentic Harness with deep tech-stack discovery via CodeGraph and enforce deterministic verification gates in the Orchestrator flow.

**Architecture:** 
1.  **Discovery:** Enhance `discovery_engine.py` to use symbol-based auditing (via grep/codegraph) for test runners.
2.  **Contract:** Store discovered verification commands in `.harness/strategy.json`.
3.  **Enforcement:** Update the Orchestrator boilerplate and `using-harness-superpowers` skill to treat the verification strategy as a mandatory hard gate for task completion.

**Tech Stack:** Python (Harness Core), Markdown (Agent Mandates/Skills), Jinja2 (Templates).

---

### Task 1: Research & Mock Discovery Environment

**Files:**
- Create: `tests/fixtures/discovery_mock/package.json`
- Create: `tests/fixtures/discovery_mock/tests/e2e/login.spec.ts`
- Modify: `tests/unit/test_discovery_engine.py`

- [ ] **Step 1: Create a mock project structure with E2E markers**
```bash
mkdir -p tests/fixtures/discovery_mock/tests/e2e
echo '{"devDependencies": {"@playwright/test": "^1.0.0"}}' > tests/fixtures/discovery_mock/package.json
echo "import { test } from '@playwright/test'; test('login', () => {});" > tests/fixtures/discovery_mock/tests/e2e/login.spec.ts
```

- [ ] **Step 2: Write a failing test for deep discovery**
```python
# tests/unit/test_discovery_engine.py
from harness.discovery_engine import detect_tech_stack

def test_deep_discovery_playwright():
    project_path = "tests/fixtures/discovery_mock"
    # We expect detect_tech_stack to now return more than just "Node.js/JavaScript"
    # It should include evidence of Playwright.
    result = detect_tech_stack(project_path)
    assert "Playwright" in result["capabilities"]
    assert result["strategy"]["e2e"] == "npx playwright test"
```

- [ ] **Step 3: Run test to verify it fails**
Run: `pytest tests/unit/test_discovery_engine.py`
Expected: FAIL (AttributeError or KeyError since detect_tech_stack currently returns a string).

---

### Task 2: Implement Language-Agnostic LLM Discovery

**Files:**
- Modify: `src/harness/discovery_engine.py`

- [ ] **Step 1: Implement "Symbol Census" via CodeGraph**
Instead of searching for hardcoded strings, extract a list of the most frequent symbols, imports, and decorators across the codebase to identify patterns.

```python
# src/harness/discovery_engine.py

def get_symbol_census(project_path: str) -> list:
    # Use CodeGraph to find:
    # 1. Top 20 imported libraries
    # 2. Common function decorators (e.g., @test, @fixture)
    # 3. File naming patterns (e.g., *.spec.*, test_*.py)
    pass

def deep_audit_discovery(project_path: str, query_llm_fn=None, **kwargs) -> dict:
    census = get_symbol_census(project_path)
    file_tree = get_file_tree_summary(project_path) # max 3 levels
    
    prompt = f"""
    Analyze this project data:
    FILE TREE: {file_tree}
    SYMBOL CENSUS: {census}
    
    Identify the testing infrastructure. For each test type (unit, e2e):
    1. What is the framework?
    2. What is the CLI command to run all tests?
    
    Return JSON: {{"unit": {{"framework": "...", "command": "..."}}, "e2e": ...}}
    """
    # ... call LLM ...
```

- [ ] **Step 2: Update `detect_tech_stack` signature and logic**
```python
def detect_tech_stack(project_path: str, query_llm_fn=None, **kwargs) -> dict:
    # Merge heuristic stack detection with LLM-driven census
    audit = deep_audit_discovery(project_path, query_llm_fn, **kwargs)
    # ...
```

- [ ] **Step 3: Run test with diverse mocks**
Test with mock data for Go (Ginkgo) and Rust (cargo test) to ensure the LLM correctly maps symbols to commands without hardcoded rules.

---

### Task 3: Strategy Persistence in Minting Engine

**Files:**
- Modify: `src/harness/minting_engine.py`

- [ ] **Step 1: Update `mint_workspace` to write `strategy.json`**
```python
# src/harness/minting_engine.py

# Inside mint_workspace, after tech_stack detection:
tech_data = detect_tech_stack(project_path)
strategy_path = target_path / "strategy.json"
with open(strategy_path, "w") as f:
    json.dump(tech_data["strategy"], f, indent=2)
```

- [ ] **Step 2: Update `generate_onboarding_domain_doc` to include verification preview**
```python
# src/harness/discovery_engine.py -> generate_onboarding_domain_doc
# Add verification section to the template string
"""
## Verification Strategy
The following commands were discovered and will be used by the @verifier:
- **Unit:** <!--$ UNIT_CMD $-->
- **E2E:** <!--$ E2E_CMD $-->
"""
```

- [ ] **Step 3: Verify minting logic with a unit test**
Run: `pytest tests/unit/test_minting_engine.py`
Expected: PASS (if updated correctly)

- [ ] **Step 4: Commit**
```bash
git add src/harness/minting_engine.py src/harness/discovery_engine.py
git commit -m "feat: persist verification strategy to strategy.json"
```

---

### Task 4: Orchestrator & Verifier Template Updates

**Files:**
- Modify: `src/harness/templates/boilerplate/orchestrator.md`
- Modify: `src/harness/templates/boilerplate/agents/verifier.md`

- [ ] **Step 1: Add Strategy Read mandate to Orchestrator**
```markdown
### DETERMINISTIC VERIFICATION:
- You MUST read `.harness/strategy.json` during your first turn.
- You are FORBIDDEN from closing a task without a `PASS` report from `@verifier`.
```

- [ ] **Step 2: Update Verifier to use the strategy file**
```markdown
### Verification Execution:
- Read `.harness/strategy.json` to identify the correct commands for this project.
- Execute the mandatory stages and report results in `QA_REPORT.md`.
```

- [ ] **Step 3: Commit**
```bash
git add src/harness/templates/boilerplate/orchestrator.md src/harness/templates/boilerplate/agents/verifier.md
git commit -m "feat: update orchestrator and verifier mandates for deterministic verification"
```

---

### Task 5: Implement Language-Agnostic Verification Skill

**Files:**
- Create: `src/harness/templates/boilerplate/skills/verification-before-completion/SKILL.md`
- Modify: `src/harness/templates/boilerplate/skills/using-harness-superpowers/SKILL.md`

- [ ] **Step 1: Create the new skill file**
```markdown
# Verification Before Completion
This skill ensures that no change is submitted without empirical proof of correctness.
1. Read `.harness/strategy.json`.
2. Identify all 'critical' stages for the current project.
3. Dispatch `@verifier` to execute those stages.
4. Ensure the `QA_REPORT.md` contains evidence of a PASS.
```

- [ ] **Step 2: Inject the gate into `using-harness-superpowers`**
```dot
# Update the dot graph in using-harness-superpowers/SKILL.md
"Verification Pass?" [shape=diamond];
"Invoke verification-before-completion" [shape=box];
# ... add edges ...
```

- [ ] **Step 3: Commit**
```bash
git add src/harness/templates/boilerplate/skills/
git commit -m "feat: implement language-agnostic verification skill and gate"
```
