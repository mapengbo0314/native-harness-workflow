# Harness Dynamic Discovery Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `harness-wf init` to use dynamic MCP discovery, remove static JSON dependencies, fix workspace minting, and integrate Superpower workflows.

**Architecture:** The CLI will clone the boilerplate first, spawn an `CodeGraph serve` subprocess to dynamically fetch context via MCP, pass that to the feature-fetcher LLM prompt, and then mint a clean workspace containing fully styled `config.yaml` and `agent.json` files.

**Tech Stack:** Python 3.10+, `CodeGraph` MCP server, `argparse`, `subprocess`.

---

### Task 1: Clean Up Legacy Scripts & Indexer Wrapper

**Files:**
- Modify: `harness/cli.py`
- Delete: `harness/indexer_wrapper.py`
- Delete: `boilerplate-agent/scripts/clone_harness.py`
- Delete: `boilerplate-agent/scripts/clone_harness.sh`
- Delete: `boilerplate-agent/scripts/setup_harness.sh`

- [ ] **Step 1: Delete legacy boilerplate scripts**

```bash
git rm boilerplate-agent/scripts/clone_harness.py
git rm boilerplate-agent/scripts/clone_harness.sh
git rm boilerplate-agent/scripts/setup_harness.sh
```

- [ ] **Step 2: Delete indexer_wrapper.py**

```bash
git rm harness/indexer_wrapper.py
```

- [ ] **Step 3: Remove indexer_wrapper references from cli.py**

Modify `harness/cli.py` to remove `check_CodeGraph_installed` and `acquire_context` imports and calls. Leave the `argparse` and credential checking intact. 

```python
import argparse
import sys
import getpass
import os

def parse_args():
    parser = argparse.ArgumentParser(description="Initialize a new Harness agent workspace.")
    parser.add_argument("command", choices=["init"], help="Command to run")
    parser.add_argument("--project-path", required=True, help="Path to the repository")
    parser.add_argument("--llm", required=True, choices=["gemini", "openai", "anthropic"], help="LLM provider")
    parser.add_argument("--model", help="Optional specific model to use (e.g., gemini-1.5-flash, claude-3-5-sonnet-20241022)")
    parser.add_argument("--bundle", help="Optional path to an existing CodeGraph JSON bundle")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Secure Credential Check
    api_key_env_var = f"{args.llm.upper()}_API_KEY"
    api_key = os.environ.get(api_key_env_var)
    if not api_key:
        print(f"Environment variable {api_key_env_var} not found.")
        api_key = getpass.getpass(prompt=f"Enter your {args.llm} API Key: ")
        
    print("Pre-flight checks passed.")
    # (Rest of main will be rewritten in subsequent tasks)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit cleanup**

```bash
git commit -m "refactor: remove legacy scripts and static indexer wrapper"
```

---

### Task 2: Implement Dynamic MCP Context Acquisition

**Files:**
- Modify: `harness/discovery_engine.py`

- [ ] **Step 1: Rewrite `discovery_engine.py` to use `subprocess` for MCP**

Replace the current contents with a robust MCP wrapper.

```python
import json
import subprocess
import time

def acquire_mcp_context(project_path: str) -> str:
    """Spawns CodeGraph serve and fetches the project summary via MCP."""
    print(f"Starting CodeGraph MCP server for dynamic analysis on {project_path}...")
    
    proc = subprocess.Popen(
        ["CodeGraph", "serve", "--stdio", project_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # 1. Initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "harness-wf", "version": "1.0.0"}
            }
        }
        proc.stdin.write(json.dumps(init_req) + "\\n")
        proc.stdin.flush()
        
        # Read init response (might be preceded by logs)
        while True:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server died during initialization.")
            if line.startswith("{"):
                break
                
        # Send initialized notification
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\\n")
        proc.stdin.flush()
        
        # 2. Call summarize tool
        call_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "summarize",
                "arguments": {"path": "."}
            }
        }
        proc.stdin.write(json.dumps(call_req) + "\\n")
        proc.stdin.flush()
        
        # Read call response
        while True:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server died while summarizing.")
            if line.startswith("{"):
                resp = json.loads(line)
                if "error" in resp:
                    raise RuntimeError(f"MCP summarize failed: {resp['error']}")
                if "result" in resp and "content" in resp["result"]:
                    return resp["result"]["content"][0]["text"]
                break
                
        return "No context available."
        
    finally:
        proc.terminate()
        proc.wait(timeout=5)
```

- [ ] **Step 2: Add LLM Query Stub & Discovery Logic**

Add the `query_llm` and `discover_agents` functions back to `harness/discovery_engine.py`, updating them to use the `feature-fetcher` prompt.

```python
def query_llm(prompt: str, llm_provider: str, api_key: str, model: str = None) -> str:
    """Stub for querying the LLM."""
    # Hardcoded stub for initial development
    return '{"agents": [{"name": "API Handler", "role": "Manages Express routes", "zone": "Handler Category"}, {"name": "DB Modeler", "role": "Manages schemas", "zone": "Data Structure Category"}]}'

def discover_agents(project_path: str, feature_fetcher_yaml_path: str, llm_provider: str, api_key: str, model: str = None) -> list[dict]:
    """Uses MCP to get context, loads the system prompt, and queries the LLM."""
    context_str = acquire_mcp_context(project_path)
    
    # Load system prompt
    system_prompt = "You are the Feature Fetcher."
    try:
        import yaml
        with open(feature_fetcher_yaml_path, 'r') as f:
            config = yaml.safe_load(f)
            if "system_prompt" in config:
                system_prompt = config["system_prompt"]
    except Exception as e:
        print(f"Warning: Could not load feature-fetcher prompt: {e}")

    full_prompt = f"{system_prompt}\\n\\nPROJECT CONTEXT:\\n{context_str}\\n\\nBased on the mandate above, output the required JSON."
    
    print(f"Querying {llm_provider} for specialized agents...")
    response_text = query_llm(full_prompt, llm_provider, api_key, model)
    
    try:
        cleaned = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        return data.get("agents", [])
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse LLM response as JSON: {e}")
        return [{"name": "Architect", "role": "General architecture and design", "zone": "Core"}]
```

- [ ] **Step 3: Commit discovery changes**

```bash
git add harness/discovery_engine.py
git commit -m "feat: implement dynamic MCP discovery engine"
```

---

### Task 3: Refactor CLI Orchestration

**Files:**
- Modify: `harness/cli.py`

- [ ] **Step 1: Update `cli.py` to clone first and use dynamic discovery**

```python
import argparse
import sys
import getpass
import os
import tempfile
import subprocess
import shutil

def parse_args():
    # ... (keep existing parse_args) ...
    parser = argparse.ArgumentParser(description="Initialize a new Harness agent workspace.")
    parser.add_argument("command", choices=["init"], help="Command to run")
    parser.add_argument("--project-path", required=True, help="Path to the repository")
    parser.add_argument("--llm", required=True, choices=["gemini", "openai", "anthropic"], help="LLM provider")
    parser.add_argument("--model", help="Optional specific model to use (e.g., gemini-1.5-flash, claude-3-5-sonnet-20241022)")
    parser.add_argument("--bundle", help="Optional path to an existing CodeGraph JSON bundle")
    return parser.parse_args()

def main():
    args = parse_args()
    
    api_key_env_var = f"{args.llm.upper()}_API_KEY"
    api_key = os.environ.get(api_key_env_var)
    if not api_key:
        print(f"Environment variable {api_key_env_var} not found.")
        api_key = getpass.getpass(prompt=f"Enter your {args.llm} API Key: ")
        
    print("Pre-flight checks passed.")
    
    print("Stage 1: Cloning boilerplate for discovery...")
    repo_url = "https://github.com/mapengbo0314/e2g.git"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.run(["git", "clone", "--depth", "1", repo_url, temp_dir], check=True, capture_output=True)
        boilerplate_dir = os.path.join(temp_dir, "boilerplate-agent")
        
        feature_fetcher_yaml = os.path.join(boilerplate_dir, "agents", "discovery", "feature-fetcher", "config.yaml")
        
        print("Stage 2: Dynamic Agent Discovery")
        from harness.discovery_engine import discover_agents
        
        # If bundle provided, we skip dynamic discovery in the stub for now or just run it on the project path
        # Assuming acquire_mcp_context handles the project_path directly
        recommended_agents = discover_agents(args.project_path, feature_fetcher_yaml, args.llm, api_key, args.model)
        
        print(f"Found {len(recommended_agents)} recommendations.")
        selected_agents = []
        print("\\n=== Recommended Agents ===")
        for idx, agent in enumerate(recommended_agents):
            print(f"[{idx}] {agent['name']} ({agent['zone']}): {agent['role']}")
            choice = input(f"Include {agent['name']}? (Y/n): ").strip().lower()
            if choice in ['', 'y', 'yes']:
                selected_agents.append(agent)
                
        if not selected_agents:
            print("No agents selected. Aborting.")
            sys.exit(0)

        print("\\n=== Platform Selection ===")
        print("1. Gemini CLI")
        print("2. Claude Code")
        print("3. Copilot CLI")
        print("4. Cursor")
        print("5. Generic / Custom")
        platform_choice = input("Select target platform [1-5]: ").strip()
        if not platform_choice:
            platform_choice = "1"
            
        print(f"\\nStage 3: Proceeding to mint {len(selected_agents)} agents...")
        
        from harness.minting_engine import mint_workspace
        target_dir = os.path.join(args.project_path, ".agents")
        
        # We pass the cloned boilerplate_dir so minting engine doesn't have to clone again
        mint_workspace(target_dir, selected_agents, args.project_path, platform_choice, args.model, args.bundle, boilerplate_dir)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit CLI refactor**

```bash
git add harness/cli.py
git commit -m "refactor: orchestrate clone-first dynamic discovery flow"
```

---

### Task 4: Refactor Minting Engine

**Files:**
- Modify: `harness/minting_engine.py`

- [ ] **Step 1: Update `mint_workspace` signature and local copy logic**

Update the signature to accept `boilerplate_dir` and remove the second github clone.

```python
import os
import shutil
import json
from pathlib import Path

def mint_workspace(target_dir: str, selected_agents: list[dict], project_path: str, platform_choice: str, model_choice: str = None, bundle_override: str = None, boilerplate_dir: str = None):
    """Copies boilerplate, injects styled configs, and writes setup prerequisites."""
    target_path = Path(target_dir)
    
    if target_path.exists():
        print(f"Warning: Target directory {target_dir} already exists. Minting may overwrite files.")
        
    def ignore_patterns(dir_path, contents):
        ignored = ['.git', '__pycache__', '.DS_Store']
        return [i for i in contents if i in ignored or i.endswith('.log')]
        
    if boilerplate_dir and os.path.exists(boilerplate_dir):
        shutil.copytree(boilerplate_dir, target_path, ignore=ignore_patterns, dirs_exist_ok=True)
    else:
        print("Error: Boilerplate directory not found.")
        return

    # Remove internal discovery agents from the final workspace
    discovery_path = target_path / "agents" / "discovery"
    if discovery_path.exists():
        shutil.rmtree(discovery_path)

    # Handle existing bundle / wiki migration
    existing_wiki = False
    if bundle_override:
        # Determine where the .codegraph folder is located based on the bundle argument
        if os.path.isdir(bundle_override) and os.path.basename(bundle_override) == ".codegraph":
            source_CodeGraph = bundle_override
        elif os.path.isdir(bundle_override):
            source_CodeGraph = os.path.join(bundle_override, ".codegraph")
        else:
            source_CodeGraph = os.path.join(os.path.dirname(bundle_override), ".codegraph")
            
        target_CodeGraph = os.path.join(project_path, ".codegraph")
        
        if os.path.exists(source_CodeGraph) and os.path.abspath(source_CodeGraph) != os.path.abspath(target_CodeGraph):
            print(f"Migrating existing wiki database from {source_CodeGraph} to {target_CodeGraph}...")
            if os.path.exists(target_CodeGraph):
                shutil.rmtree(target_CodeGraph)
            shutil.copytree(source_CodeGraph, target_CodeGraph)
            
        if os.path.exists(os.path.join(target_CodeGraph, "wiki")):
            existing_wiki = True
            
    # Generate specialized setup_harness.sh (Prerequisites)
    CodeGraph_init_flag = ""
    if platform_choice == "1":
        platform_name = "Gemini CLI"
    elif platform_choice == "2":
        platform_name = "Claude Code"
        CodeGraph_init_flag = " --claude"
    elif platform_choice == "3":
        platform_name = "Copilot CLI"
    elif platform_choice == "4":
        platform_name = "Cursor"
        CodeGraph_init_flag = " --cursor"
    else:
        platform_name = "Generic / Custom"

    setup_script_path = target_path / "scripts" / "setup_harness.sh"
    setup_script_path.parent.mkdir(parents=True, exist_ok=True)
    
    setup_content = f"""#!/usr/bin/env bash
set -e
echo "=== Setting up Agentic Harness Prerequisites for {platform_name} ==="

# 1. Platform Specific Extension/Skill Installation
"""
    if platform_choice == "1": # Gemini
        setup_content += """
echo "Installing Superpowers for Gemini CLI..."
if command -v gemini &> /dev/null; then
    gemini extensions install https://github.com/obra/superpowers || true
else
    echo "Warning: gemini command not found."
fi
"""
    elif platform_choice == "2": # Claude
        setup_content += """
echo "To install Superpowers for Claude Code, run this command inside the Claude Code interface:"
echo "  /plugin install superpowers@claude-plugins-official"
"""
    elif platform_choice == "3": # Copilot
        setup_content += """
echo "Installing Superpowers for Copilot CLI..."
if command -v copilot &> /dev/null; then
    copilot plugin marketplace add obra/superpowers-marketplace || true
    copilot plugin install superpowers@superpowers-marketplace || true
else
    echo "Warning: copilot command not found."
fi
"""
    elif platform_choice == "4": # Cursor
        setup_content += """
echo "To install Superpowers for Cursor, run this command inside the Cursor Agent chat:"
echo "  /add-plugin superpowers"
"""
    else: # Generic fallback
        setup_content += """
echo "Please refer to https://github.com/obra/superpowers to manually install skills for your AI platform."
"""

    setup_content += f"""
# 2. Install CodeGraph MCP Server
echo "Installing CodeGraph MCP Server..."
if command -v cargo &> /dev/null; then
    cargo install CodeGraph --features wiki,http || true
    CodeGraph init{CodeGraph_init_flag} || true
else
    echo "Error: cargo required to install CodeGraph. Visit https://rustup.rs/"
fi
"""

    if existing_wiki:
        setup_content += """
# 3. Existing Wiki Detected
echo "Existing codebase wiki database detected. Skipping initial wiki generation."
"""
    else:
        setup_content += f"""
# 3. Generate initial Codebase Wiki
echo "Generating initial codebase wiki (this may take a moment)..."
(cd "{os.path.abspath(project_path)}" && CodeGraph wiki generate{" --model " + model_choice if model_choice else ""}) || echo "Warning: Wiki generation failed. You may need to run it manually."
"""

    with open(setup_script_path, "w") as f:
        f.write(setup_content)
    os.chmod(setup_script_path, 0o755)
    
    # Generate Platform Rules file (GEMINI.md, CLAUDE.md, etc.)
    rules_file = "GEMINI.md" if platform_choice == "1" else "CLAUDE.md" if platform_choice == "2" else "RULES.md"
    rules_content = f"""# Agentic Harness Rules for {platform_name}

1. **Context First**: Always use the `CodeGraph` MCP server to query the codebase before proposing changes.
2. **Strict Planning**: Never write production code without an approved plan in `workspace/artifacts/plan.md`.
3. **Superpower Workflows**: You MUST utilize installed Superpower skills (e.g., brainstorming, writing-plans, test-driven-development) during execution.
"""
    with open(target_path / rules_file, "w") as f:
        f.write(rules_content)

    # Create an MCP config that points to the CodeGraph server running in the project root
    CodeGraph_serve_args = ["serve", "--stdio", "--watch", "--wiki-auto-update"]
    if model_choice:
        CodeGraph_serve_args.extend(["--wiki-model", model_choice])
    
    CodeGraph_serve_cmd = " ".join(CodeGraph_serve_args)

    mcp_config = {
        "mcpServers": {
            "CodeGraph": {
                "command": "bash",
                "args": ["-c", f"cd {os.path.abspath(project_path)} && CodeGraph {CodeGraph_serve_cmd}"],
                "env": {
                    "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
                    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
                    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "")
                }
            }
        }
    }
    
    mcp_path = target_path / "mcp.json"
    with open(mcp_path, 'w') as f:
         json.dump(mcp_config, f, indent=2)
         
    # Generate Specialized Agents
    specialized_dir = target_path / "agents" / "specialized"
    specialized_dir.mkdir(exist_ok=True, parents=True)
    
    for agent in selected_agents:
        safe_name = agent["name"].lower().replace(" ", "-")
        agent_dir = specialized_dir / safe_name
        agent_dir.mkdir(exist_ok=True, parents=True)
        
        # Inject agent.json
        agent_manifest = {
            "name": agent["name"],
            "description": agent["role"],
            "entrypoint": "config.yaml"
        }
        with open(agent_dir / "agent.json", 'w') as f:
            json.dump(agent_manifest, f, indent=2)
            
        # Inject config.yaml
        config_yaml_content = f"""coding_agent: true
agentic_mode: true
prompt_section_customization:
  add_prompt_sections:
  - prompt_section:
      title: Core Mandates
      content: |
        You are a specialized subagent operating within this repository's agent ecosystem.
        You have been delegated a specific task by the Orchestrator.
        1. Security & System Integrity: Protect secrets.
        2. Context Efficiency: Be strategic in tool usage.
        3. Superpower Workflows: You MUST utilize installed Superpower skills.
    insert_before_sections: artifacts
  - prompt_section:
      title: Indexer MCP Integration
      content: |
        You have access to the codebase index via the `CodeGraph` MCP server.
        - Strategic Fetching: Use `find`, `summarize`, `get_file_summary` via MCP.
    insert_after_sections: Core Mandates
  - prompt_section:
      title: 'Role: {agent["name"]}'
      content: |
        You are {agent["name"]}.
        Zone: {agent["zone"]}
        Responsibilities: {agent["role"]}
        
        SUPERPOWER MANDATE: You MUST invoke relevant superpower skills before finalizing work.
    insert_after_sections: Indexer MCP Integration
"""
        with open(agent_dir / "config.yaml", 'w') as f:
            f.write(config_yaml_content)
            
    print(f"Successfully minted workspace at {target_dir}")
    print("\\nNext Steps:")
    print(f"1. cd {target_dir}")
    print("2. ./scripts/setup_harness.sh (Install prerequisites)")
    print("3. Activate your environment and Launch AI")
```

- [ ] **Step 2: Commit minting engine refactor**

```bash
git add harness/minting_engine.py
git commit -m "feat: implement styled agent generation and fix directory duplication"
```

---

### Task 5: Install & Package Validation

- [ ] **Step 1: Install the package locally**

```bash
pip install -e .
```

- [ ] **Step 2: Dry-run `harness-wf init`**

Run the command to ensure it parses correctly (the actual execution requires the real LLM endpoint, but we can verify imports and argument passing).

```bash
harness-wf init --help
```