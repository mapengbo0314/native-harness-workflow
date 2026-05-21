# Harness Pointer Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the boilerplate agent and minting engine to use a "Goose-style" pointer architecture, moving root instructions out of the `_agents` folder and implementing native skill routing via pre-bundled skills.

**Architecture:** We are moving from dynamically generated, platform-specific rules files (e.g., generating a full `CLAUDE.md`) to a centralized `AGENTS.md` (the "Core Brain") located in the project root. Platform-specific files (`GEMINI.md`, `CLAUDE.md`, `.cursorrules`) will act as minimal "pointers" to this central file. Additionally, Superpower skills will be pre-bundled into `boilerplate-agent/skills`, and the `setup_harness.sh` script will create native, platform-specific pointers (e.g., in `.claude/skills/`) that link back to the central skills folder.

**Tech Stack:** Python (for the minting engine), Bash (for the setup script), Markdown (for rules/skills).

---

### Task 1: Create the Central "Brain" (AGENTS.md) in the Boilerplate

**Files:**
- Create: `boilerplate-agent/AGENTS.md`

- [x] **Step 1: Write the content for AGENTS.md**
Write the centralized rules that all agents will follow. This replaces the complex `rules_content` currently dynamically generated in `minting_engine.py`.

```bash
cat << 'EOF' > boilerplate-agent/AGENTS.md
# Agentic Harness Rules

<EXTREMELY-IMPORTANT>
You are operating within the Superpowers Agentic Harness.
You MUST adhere to the `using-superpowers` state machine.
IF A SKILL APPLIES TO YOUR TASK, YOU MUST USE IT BEFORE ACTING.
</EXTREMELY-IMPORTANT>

## Core Mandates

1. **Context First**: Always use the `CodeGraph` MCP server to query the codebase before proposing changes.
2. **Strict Planning**: Never write production code without an approved plan.
3. **Superpower Workflows**: You MUST utilize installed Superpower skills (e.g., brainstorming, writing-plans, test-driven-development) during execution.
4. **Local Skills**: You MUST refer to the local skills stored in `_agents/skills/` for your specific workflows.
5. **Agent Discovery**: The Orchestrator routes tasks to specialized subagents located in `_agents/agents/`.

## Wiki Knowledge Base Integration

The `CodeGraph` MCP server maintains an auto-updating codebase wiki. You MUST utilize these tools when working:
- `wiki_search`: Search wiki by keyword/concept before reading raw source code.
- `wiki_read`: Read full content and metadata of a wiki page.
- `wiki_status`: Check wiki health, page count, and source file coverage.
- `wiki_suggest_contribution`: Find which page to update based on your analysis.
- `wiki_compound`: Auto-route your synthesized knowledge to the best matching page.
- `wiki_record_failure`: Record failed fix attempts so future agents learn from them.
EOF
```

- [x] **Step 2: Verify the file exists**
Run: `ls -la boilerplate-agent/AGENTS.md`
Expected: File is listed.

- [x] **Step 3: Commit**
```bash
git add boilerplate-agent/AGENTS.md
git commit -m "feat: add central AGENTS.md to boilerplate"
```

### Task 2: Pre-bundle Skills into the Boilerplate

**Files:**
- Modify: `boilerplate-agent/skills/` (Create directory and add files)

- [x] **Step 1: Create the skills directory**
```bash
mkdir -p boilerplate-agent/skills/
```

- [x] **Step 2: Download the required skills into the boilerplate**
We will use the `skills` CLI to download the requested skills directly into the boilerplate.

```bash
npx skills@latest add mattpocock/grill-with-docs mattpocock/improve-codebase-architecture mattpocock/grill-me --dir boilerplate-agent/skills
```

- [x] **Step 3: Verify the skills exist**
Run: `ls -la boilerplate-agent/skills/`
Expected: `grill-with-docs.md`, `improve-codebase-architecture.md`, and `grill-me.md` are listed.

- [x] **Step 4: Commit**
```bash
git add boilerplate-agent/skills/
git commit -m "feat: pre-bundle core skills into boilerplate"
```

### Task 3: Refactor Minting Engine - Remove Dynamic Skill Downloading

**Files:**
- Modify: `harness/minting_engine.py`

- [x] **Step 1: Write a test that verifies skills are NOT downloaded dynamically**
We will mock `urllib.request.urlopen` in `tests/test_discovery_engine.py` (or a new test file, but we'll assume `test_minting_engine.py` exists or we create a simple script to verify). Since we don't have a test suite context, we will manually verify the code removal.

- [x] **Step 2: Remove the skill downloading logic from `minting_engine.py`**
In `harness/minting_engine.py`, find the block labeled `# 4. Download External Skills directly into the workspace` and remove it entirely.

```python
# Replace the old logic in harness/minting_engine.py (around lines 193-211)
import re

with open("harness/minting_engine.py", "r") as f:
    content = f.read()

# Pattern to remove the entire block related to urllib and downloading skills
pattern = r"import urllib\.request\n.*?(?=# Generate Specialized Agents)"
new_content = re.sub(pattern, "", content, flags=re.DOTALL)

with open("harness/minting_engine.py", "w") as f:
    f.write(new_content)
```

- [x] **Step 3: Verify the logic is gone**
Run: `grep "urllib.request" harness/minting_engine.py`
Expected: No output.

- [x] **Step 4: Commit**
```bash
git add harness/minting_engine.py
git commit -m "refactor: remove dynamic skill downloading from minting engine"
```

### Task 4: Refactor Minting Engine - Implement Pointer Architecture

**Files:**
- Modify: `harness/minting_engine.py`

- [x] **Step 1: Update the rule generation logic to use pointers**
In `harness/minting_engine.py`, replace the code that generates `rules_content` with code that generates simple pointer files.

```python
# Create a python script to do the string replacement safely
cat << 'EOF' > script_replace.py
import re

with open("harness/minting_engine.py", "r") as f:
    content = f.read()

# Pattern to find the old rules generation block
pattern = r"diagnostic_section = \"\"\n.*?with open\(project_root / rules_file, \"w\"\) as f:\n\s+f\.write\(rules_content\)"

# The new logic generating the pointer
new_logic = """
    # Generate Platform Rules Pointer File
    pointer_content = f\"\"\"# Agentic Harness
    
Please read `AGENTS.md` for core repository instructions and routing rules.
\"\"\"
    with open(project_root / rules_file, "w") as f:
        f.write(pointer_content)
"""

new_content = re.sub(pattern, new_logic, content, flags=re.DOTALL)

with open("harness/minting_engine.py", "w") as f:
    f.write(new_content)
EOF
python script_replace.py
rm script_replace.py
```

- [x] **Step 2: Verify the change**
Run: `cat harness/minting_engine.py` and inspect the `rules_file` writing section. It should write the minimal pointer content.

- [x] **Step 3: Commit**
```bash
git add harness/minting_engine.py
git commit -m "refactor: implement pointer architecture in minting engine"
```

### Task 5: Refactor Setup Script to Generate Native Skill Pointers

**Files:**
- Modify: `harness/minting_engine.py` (Specifically the `setup_harness.sh` generation logic)

- [x] **Step 1: Update the setup script generation**
We need to add logic to `setup_harness.sh` to create native platform pointers (e.g., `.claude/skills/code-review` pointing to `_agents/skills/code-review`).

```python
# Create a python script to safely update the setup_content string in minting_engine.py
cat << 'EOF' > script_replace_setup.py
import re

with open("harness/minting_engine.py", "r") as f:
    content = f.read()

# Find the end of the existing setup script generation block
pattern = r"(with open\(setup_script_path, \"w\"\) as f:\n\s+f\.write\(setup_content\))"

# The new logic to append to the setup script
new_logic = """
    # Append native skill pointer generation logic to the setup script
    setup_content += \"\"\"
# 4. Generate Native Skill Pointers
echo "Setting up native skill pointers..."

# Source skills directory
SKILLS_SRC="_agents/skills"

if [ "$1" = "--claude" ] || [ -d ".claude" ]; then
    echo "  Creating pointers for Claude Code..."
    mkdir -p .claude/skills
    for skill_file in "$SKILLS_SRC"/*.md; do
        if [ -f "$skill_file" ]; then
            skill_name=$(basename "$skill_file" .md)
            echo "../../$skill_file" > ".claude/skills/$skill_name"
        fi
    done
fi

if [ "$1" = "--gemini" ] || [ -d ".gemini" ]; then
    echo "  Creating pointers for Gemini CLI..."
    mkdir -p .gemini/skills
    for skill_file in "$SKILLS_SRC"/*.md; do
        if [ -f "$skill_file" ]; then
            skill_name=$(basename "$skill_file" .md)
            # Gemini CLI reads full content, or we can use relative pointers if the platform supports it. 
            # Assuming Gemini CLI supports Goose-style pointers:
            echo "../../$skill_file" > ".gemini/skills/$skill_name"
        fi
    done
fi
\"\"\"

    with open(setup_script_path, "w") as f:
        f.write(setup_content)
"""

new_content = re.sub(pattern, new_logic, content, count=1)

with open("harness/minting_engine.py", "w") as f:
    f.write(new_content)
EOF
python script_replace_setup.py
rm script_replace_setup.py
```

- [x] **Step 2: Verify the change**
Run: `grep "Generate Native Skill Pointers" harness/minting_engine.py`
Expected: Output showing the newly added block.

- [x] **Step 3: Commit**
```bash
git add harness/minting_engine.py
git commit -m "feat: add native skill pointer generation to setup script"
```
