# Omni-Compatible Finalization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:dispatching-parallel-agents to execute independent tasks concurrently.

**Goal:** Fix the remaining minting engine bugs: preserve discovery agents, flatten specialized agents into `.md` files, generate root Omni-Pointers, and output segregated `setup_harness.sh` scripts for each platform.

**Architecture:** `minting_engine.py` will be modified in independent code blocks. The script generation will change from writing one `scripts/setup_harness.sh` to writing multiple `.platform/scripts/setup_harness.sh` files. Specialized agents will be written as standard Markdown files with YAML frontmatter instead of `config.yaml` / `agent.json`.

**Tech Stack:** Python.

---

### Task 1: Preserve Discovery Agents & Implement Omni-Pointers

**Files:**
- Modify: `harness/minting_engine.py`

- [x] **Step 1: Remove the deletion of the discovery folder**
In `harness/minting_engine.py`, find the block:
```python
    # Remove internal discovery agents from the final workspace
    discovery_path = target_path / "agents" / "discovery"
    if discovery_path.exists():
        shutil.rmtree(discovery_path)
```
And completely remove it.

- [x] **Step 2: Add the Omni-Pointer generation loop**
Towards the bottom of the script (around the old MCP config), inject the loop that writes the pointers to the project root.

```python
import re
with open("harness/minting_engine.py", "r") as f:
    content = f.read()

pattern = r"(# Create an MCP config that points to the CodeGraph server running in the project root)"
new_logic = """    # Generate Platform Rules Pointers IN THE ROOT DIRECTORY
    pointer_content = \"\"\"# Agentic Harness
    
Please read `AGENTS.md` for core repository instructions and routing rules.
\"\"\"
    pointer_files = ["GEMINI.md", "CLAUDE.md", ".cursorrules"]
    for rules_file in pointer_files:
        with open(project_root / rules_file, "w") as f:
            f.write(pointer_content)
            
    copilot_dir = project_root / ".github"
    copilot_dir.mkdir(exist_ok=True)
    with open(copilot_dir / "copilot-instructions.md", "w") as f:
        f.write(pointer_content)

    \\1"""

new_content = re.sub(pattern, new_logic, content)
with open("harness/minting_engine.py", "w") as f:
    f.write(new_content)
```

- [x] **Step 3: Verify the changes**
Run: `grep "Generate Platform Rules Pointers" harness/minting_engine.py`

- [x] **Step 4: Commit**
```bash
git add harness/minting_engine.py
git commit -m "fix: preserve discovery agents and implement omni-pointers"
```

### Task 2: Implement Segregated Setup Scripts

**Files:**
- Modify: `harness/minting_engine.py`

- [x] **Step 1: Replace the single `setup_harness.sh` logic with segregated scripts**
Replace the entire bash string generation section in `minting_engine.py` with this logic:

```python
import re
with open("harness/minting_engine.py", "r") as f:
    content = f.read()

# Replace everything from setup_script_path = ... down to os.chmod
pattern = r"setup_script_path = target_path / \"scripts\" / \"setup_harness\.sh\".*?os\.chmod\(setup_script_path, 0o755\)"

new_logic = """    # Generate Segregated Setup Scripts
    scripts_to_generate = {
        ".gemini": \"\"\"#!/usr/bin/env bash
set -e
echo "=== Setting up Superpowers for Gemini CLI ==="
if command -v gemini &> /dev/null; then
    gemini extensions install https://github.com/obra/superpowers || true
    gemini extensions install https://github.com/mattpocock/skills || true
else
    echo "Warning: gemini command not found."
fi
echo "Setting up native skill pointers..."
mkdir -p .gemini/skills
for skill_file in _agents/skills/*.md; do
    if [ -f "$skill_file" ]; then
        skill_name=$(basename "$skill_file" .md)
        echo "../../$skill_file" > ".gemini/skills/$skill_name"
    fi
done
\"\"\",
        ".claude": f\"\"\"#!/usr/bin/env bash
set -e
echo "=== Setting up Superpowers for Claude Code ==="
echo "To install Superpowers and Skills for Claude Code, run these commands inside the Claude Code interface:"
echo "  /plugin install superpowers@claude-plugins-official"
echo "  /plugin install skills@mattpocock"
echo "Setting up native skill pointers..."
mkdir -p .claude/skills
for skill_file in _agents/skills/*.md; do
    if [ -f "$skill_file" ]; then
        skill_name=$(basename "$skill_file" .md)
        echo "../../$skill_file" > ".claude/skills/$skill_name"
    fi
done
# MCP Configuration for Claude
if command -v claude &> /dev/null; then
    echo "Adding CodeGraph to Claude Code global MCP configuration..."
    escaped_project_path="{os.path.abspath(project_path).replace("'", "'\\\\''")}"
    CodeGraph_serve_args_str="serve --watch --wiki-auto-update"
    claude mcp add CodeGraph bash -c "cd '$escaped_project_path' && CodeGraph $CodeGraph_serve_args_str" || true
fi
\"\"\",
        ".cursor": \"\"\"#!/usr/bin/env bash
set -e
echo "=== Setting up Superpowers for Cursor ==="
echo "To install Superpowers and Skills for Cursor, run these commands inside the Cursor Agent chat:"
echo "  /add-plugin superpowers"
echo "  /add-plugin mattpocock/skills"
\"\"\"
    }

    for platform_dir, script_content in scripts_to_generate.items():
        script_dir = project_root / platform_dir / "scripts"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_path = script_dir / "setup_harness.sh"
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        
    print("\\nTo install skills & MCPs, run the setup_harness.sh script inside your platform's hidden folder (e.g. `sh .gemini/scripts/setup_harness.sh`).")
"""

new_content = re.sub(pattern, new_logic, content, flags=re.DOTALL)
with open("harness/minting_engine.py", "w") as f:
    f.write(new_content)
```

- [x] **Step 2: Commit**
```bash
git add harness/minting_engine.py
git commit -m "feat: implement segregated setup scripts per platform"
```

### Task 3: Flatten Specialized Agents into single `.md` files

**Files:**
- Modify: `harness/minting_engine.py`

- [x] **Step 1: Replace specialized agent JSON/YAML generation with Markdown Frontmatter**
Find the block labeled `# Generate Specialized Agents` and rewrite the loop to output a single `.md` file.

```python
import re
with open("harness/minting_engine.py", "r") as f:
    content = f.read()

# Replace the loop under `# Generate Specialized Agents`
pattern = r"for agent in selected_agents:.*?(?=print\(f\"Successfully minted workspace)"

new_logic = """for agent in selected_agents:
        safe_name = agent["name"].lower().replace(" ", "-")
        agent_dir = specialized_dir / safe_name
        agent_dir.mkdir(exist_ok=True, parents=True)
        
        agent_file_path = agent_dir / f"{safe_name}.md"
        
        frontmatter = f\"\"\"---
name: {agent["name"]}
description: {agent["role"]}
coding_agent: true
agentic_mode: true
---
\"\"\"
        system_prompt = agent.get("system_prompt", f"# {agent['name']}\\n\\n{agent['role']}")
        
        # Append DDD logic
        ddd_section = ""
        if ddd_context:
            ddd_section = f\"\"\"
## Domain-Driven Design (DDD) Context
This project uses Domain-Driven Design principles.
At the beginning of any new session or task involving domain logic, you MUST use the `read_file` tool to load `{target_path.name}/ddd/context.md`.

You MUST refer to the following DDD documentation:
- `context.md`: Defines the core domain terms and their meanings.
- `translation_map.json`: Maps domain concepts to implementation details.

Ensure your implementation aligns with these definitions.
\"\"\"

        core_mandates = f\"\"\"
## Core Mandates
You are a specialized subagent operating within this repository's agent ecosystem.
You have been delegated a specific task by the Orchestrator.
1. Security & System Integrity: Protect secrets.
2. Context Efficiency: Be strategic in tool usage.
3. Superpower Workflows: You MUST run `list_directory` on `{target_path.name}/skills/` at the start of your session to discover available local skills.

## Indexer MCP Integration
You have access to the codebase index via the `CodeGraph` MCP server.
- Strategic Fetching: Use `find`, `summarize`, `get_file_summary` via MCP.
\"\"\"

        final_content = frontmatter + system_prompt + "\\n" + core_mandates + "\\n" + ddd_section
        
        with open(agent_file_path, 'w') as f:
            f.write(final_content)
            
    """

new_content = re.sub(pattern, new_logic, content, flags=re.DOTALL)
with open("harness/minting_engine.py", "w") as f:
    f.write(new_content)
```

- [x] **Step 2: Commit**
```bash
git add harness/minting_engine.py
git commit -m "refactor: flatten specialized agents into single markdown files"
```
