# Token Optimizer Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `token-optimizer` subagent and an accompanying `efficiency_suite.py` to measure and fix token inefficiencies across the harness.

**Architecture:** A modular Python test suite provides metrics to a specialized subagent, which analyzes and proposes fixes for prompt deduplication and context leaks.

**Tech Stack:** Python, `google-genai` SDK (for token counting), Markdown.

---

### Task 1: Refactor Benchmark to Efficiency Suite

**Files:**
- Create: `tests/benchmarks/efficiency_suite.py`
- Modify: `scripts/benchmark_efficiency_test.py` (deprecated after migration)

- [ ] **Step 1: Create the base `efficiency_suite.py` with static analysis**

```python
import os
import argparse
from pathlib import Path
from google import genai

def count_tokens(text: str, model: str = "gemini-1.5-flash") -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return max(1, len(text) // 4)
    client = genai.Client(api_key=api_key)
    try:
        return client.models.count_tokens(model=model, contents=text).total_tokens
    except: return max(1, len(text) // 4)

def test_static(target_dir: Path):
    print(f"--- Static Analysis: {target_dir} ---")
    md_files = list(target_dir.rglob("*.md"))
    results = []
    for f in md_files:
        content = f.read_text()
        results.append({"file": str(f), "tokens": count_tokens(content)})
    
    # Simple overlap check: find common lines > 20 chars
    line_map = {}
    for f in md_files:
        lines = [l.strip() for l in f.read_text().splitlines() if len(l.strip()) > 20]
        for l in lines:
            if l not in line_map: line_map[l] = []
            line_map[l].append(str(f))
            
    overlaps = {l: files for l, files in line_map.items() if len(files) > 1}
    print(f"Found {len(overlaps)} redundant string patterns across {len(md_files)} files.")
    return overlaps

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-static", type=str)
    args = parser.parse_args()
    if args.test-static:
        test_static(Path(args.test_static))
```

- [ ] **Step 2: Add Goldfish Simulation Mode**

```python
def test_goldfish(doc_path: Path):
    print(f"--- Goldfish Simulation: {doc_path} ---")
    doc_content = doc_path.read_text()
    # Simulate loading referenced files
    referenced_tokens = 0
    # ... logic to parse [file](path) ...
    total_payload = count_tokens(doc_content) + referenced_tokens
    print(f"Goldfish Payload: {total_payload} tokens")
    return total_payload
```

- [ ] **Step 3: Commit**
```bash
git add tests/benchmarks/efficiency_suite.py
git commit -m "feat: implement modular efficiency suite with static and goldfish tests"
```

### Task 2: Create Token Optimizer Agent Persona

**Files:**
- Create: `_agents/agents/token-optimizer.md`
- Modify: `_agents/agents.json`

- [ ] **Step 1: Write the agent prompt**

```markdown
# Token Optimizer Agent

You are an expert in LLM context management and token efficiency. Your goal is to minimize the "token tax" of the harness without losing functional context.

## Core Mandates
1. **Never sacrifice clarity for tokens**: If a rule is critical for safety or correctness, it stays.
2. **Interactive Proposals**: Always present a table of findings and a numbered plan before editing files.
3. **Verified Goldfish**: Ensure any reduction in design doc size doesn't break the Phase 3 Goldfish comprehension test.

## Tools
- `run_shell_command("python3 tests/benchmarks/efficiency_suite.py --test-static _agents/")`
- `run_shell_command("python3 tests/benchmarks/efficiency_suite.py --test-goldfish <path>")`
```

- [ ] **Step 2: Register agent in agents.json**

```json
{
  "name": "token-optimizer",
  "description": "Measures and optimizes token usage across the harness.",
  "location": "agents/token-optimizer.md"
}
```

- [ ] **Step 3: Commit**
```bash
git add _agents/agents/token-optimizer.md _agents/agents.json
git commit -m "feat: create token-optimizer agent persona"
```

### Task 3: Holistic Integration with boilerplate-agent

**Files:**
- Create: `boilerplate-agent/agents/token-optimizer.md`
- Modify: `boilerplate-agent/agents.json`

- [ ] **Step 1: Copy/Link agent to boilerplate-agent**
- [ ] **Step 2: Update boilerplate agents.json**
- [ ] **Step 3: Run baseline test**
```bash
python3 tests/benchmarks/efficiency_suite.py --test-static boilerplate-agent/
```
- [ ] **Step 4: Commit**
```bash
git commit -m "feat: integrate token-optimizer with boilerplate-agent"
```
