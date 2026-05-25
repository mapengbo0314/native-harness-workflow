# Design Doc: Phase 5 - Prompt Assembly and Context Economy

## Problem Statement
The current agent harness suffers from prompt bloat because it recursively expands markdown documents (such as full agent prompts and skills) into the context window. This uses too many tokens, making the system slow and prone to context window limits.

## Proposed Design
1. **Context Pointers:** Instead of inlining full markdown files, `src/harness/dispatcher.py` will assemble branch-specific prompts by inserting context pointers (e.g., file paths) and instructions to read them on demand.
2. **On-Demand Skills:** We will generate an index of skills (`skills_index.json`) mapping skill names to their descriptions and paths.
3. **Activation Script:** We will implement `scripts/activate_skill.py` which takes a skill name, reads the `skills_index.json`, and outputs the skill's full content. Agents can run this script to load a skill dynamically rather than having all skills embedded in their system prompt.
4. **Dispatcher Update:** Modify `src/harness/dispatcher.py` to intercept the prompt assembly and inject pointers and the instruction to use `activate_skill.py`.

## Alternatives
- **Function Calling/MCP Tool:** Create a full MCP tool for skill activation. Rejected for now because a simple Python script (`activate_skill.py`) works immediately within the existing `run_shell_command` or similar environments without needing an MCP server restart.
- **RAG for Context:** Rejected as overkill; direct pointers to files are simpler and more deterministic.

## Sphinch Marks
- [ ] `scripts/activate_skill.py` exists and is executable.
- [ ] `scripts/activate_skill.py <skill_name>` outputs the skill content if found, or an error if not found.
- [ ] `skills_index.json` exists and contains at least `harness-writing-plans`, `harness-brainstorming`, etc.
- [ ] `src/harness/dispatcher.py` contains logic to output context pointers instead of full markdown text for skills/agents.

---

# Phase 5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce prompt bloat through branch-specific context and pointers.

**Architecture:** Modify `src/harness/dispatcher.py` to tailor the context passed to the subagent based on its branch. Implement a `scripts/activate_skill.py` script to allow loading skills on demand, tracking them in `.gemini/skills_index.json`.

**Tech Stack:** Python 3, JSON

---

### Task 1: Generate `skills_index.json`

**Files:**
- Create: `scripts/generate_skills_index.py`
- Modify: None
- Test: Manual execution

- [ ] **Step 1: Write the generation script**

```python
# scripts/generate_skills_index.py
import json
import os
from pathlib import Path

def generate_index():
    skills_dir = Path(".gemini/skills")
    index = {}
    
    if not skills_dir.exists():
        print(f"Skills directory not found at {skills_dir}")
        return

    for skill_path in skills_dir.glob("*/SKILL.md"):
        skill_name = skill_path.parent.name
        # Simple extraction of description if available
        content = skill_path.read_text()
        description = "No description available."
        for line in content.splitlines():
            if line.startswith("description:"):
                description = line.split("description:", 1)[1].strip()
                break
                
        index[skill_name] = {
            "path": str(skill_path),
            "description": description
        }
        
    index_path = Path(".gemini/skills_index.json")
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    print(f"Generated {index_path} with {len(index)} skills.")

if __name__ == "__main__":
    generate_index()
```

- [ ] **Step 2: Run the script to generate the index**

Run: `python3 scripts/generate_skills_index.py`
Expected: Output showing the number of skills generated and `.gemini/skills_index.json` is created.

- [ ] **Step 3: Commit**

```bash
git add scripts/generate_skills_index.py .gemini/skills_index.json
git commit -m "feat: add skill index generator and generated index"
```

### Task 2: Create `scripts/activate_skill.py`

**Files:**
- Create: `scripts/activate_skill.py`
- Modify: None
- Test: Execute script

- [ ] **Step 1: Write the activation script**

```python
# scripts/activate_skill.py
import json
import sys
from pathlib import Path

def activate_skill(skill_name: str):
    index_path = Path(".gemini/skills_index.json")
    if not index_path.exists():
        print("Error: skills_index.json not found. Run generate_skills_index.py first.")
        sys.exit(1)
        
    with open(index_path, "r") as f:
        index = json.load(f)
        
    if skill_name not in index:
        print(f"Error: Skill '{skill_name}' not found in index.")
        print(f"Available skills: {', '.join(index.keys())}")
        sys.exit(1)
        
    skill_path = Path(index[skill_name]["path"])
    if not skill_path.exists():
        print(f"Error: Skill file not found at {skill_path}")
        sys.exit(1)
        
    print(f"--- ACTIVE SKILL: {skill_name} ---")
    print(skill_path.read_text())
    print(f"--- END SKILL: {skill_name} ---")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python activate_skill.py <skill_name>")
        sys.exit(1)
    activate_skill(sys.argv[1])
```

- [ ] **Step 2: Make it executable and test**

Run: `chmod +x scripts/activate_skill.py && python3 scripts/activate_skill.py harness-writing-plans`
Expected: Output showing the skill content.

- [ ] **Step 3: Commit**

```bash
git add scripts/activate_skill.py
git commit -m "feat: implement activate_skill.py for on-demand context loading"
```

### Task 3: Update `src/harness/dispatcher.py` to assemble branch-specific context

**Files:**
- Modify: `src/harness/dispatcher.py`
- Test: `tests/unit/test_dispatcher.py` (assuming it exists, otherwise manual test)

- [ ] **Step 1: Modify `OrchestratorDispatcher` to inject context pointers**

Edit `src/harness/dispatcher.py` to add `assemble_prompt` and update `dispatch_agent`. We want to pass a pointer to the skill index instead of the raw content if possible, or append pointers to the `context`.

```python
# In src/harness/dispatcher.py, inside OrchestratorDispatcher class

    def assemble_branch_context(self, agent_name: str, intent_branch: str) -> str:
        """Assemble a branch-specific context pointer string to reduce prompt bloat."""
        pointers = []
        pointers.append(f"Agent Persona: {agent_name}")
        pointers.append(f"Routing Branch: {intent_branch}")
        
        # Add dynamic pointers rather than full text
        pointers.append("Available Skills Index: .gemini/skills_index.json")
        pointers.append("To load a skill, run: python3 scripts/activate_skill.py <skill_name>")
        
        if intent_branch == "A":
            pointers.append("Branch A (Bug Fix): Focus on stack traces and isolate the error. Use mcp_codegraph_codegraph_callers.")
        elif intent_branch == "B":
            pointers.append("Branch B (Feature/Arch): Focus on step-by-step planning. Use harness-brainstorming and harness-writing-plans.")
        elif intent_branch == "C":
            pointers.append("Branch C (Question): Do not modify files. Use codegraph to explore.")
        elif intent_branch == "D":
            pointers.append("Branch D (Surgical Edit): Bypass heavy planning. Use implementer directly.")
            
        return "\n".join(pointers)
```

- [ ] **Step 2: Update `dispatch_agent` to use it**

In `src/harness/dispatcher.py`, inside `dispatch_agent`, append the pointers to the returned context:

```python
        # (Inside dispatch_agent, right before return statement)
        
        branch_pointers = self.assemble_branch_context(agent_name, intent_branch)
        context["branch_context_pointers"] = branch_pointers

        return {
            "agent": agent_name,
            "routed": True,
            "context": context,
            "orchestrator_applied": True,
            "intent_branch": intent_branch,
            "intent_justification": intent_justification,
            "state": state
        }
```

- [ ] **Step 3: Run existing tests to ensure no regressions**

Run: `pytest tests/` (or specific dispatcher tests if they exist)
Expected: Tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/harness/dispatcher.py
git commit -m "refactor: update dispatcher to use branch-specific context pointers to reduce prompt bloat"
```

## Verification
- Test executing the dispatcher logic manually or via the orchestrator to ensure the `branch_context_pointers` field is populated.
- Verify `scripts/activate_skill.py` works seamlessly to fetch the actual skills instead of requiring them in the main context window.
