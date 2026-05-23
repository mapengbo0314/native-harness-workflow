import os
import re
import shutil
import json
import urllib.request
from pathlib import Path
from jinja2 import Environment, BaseLoader
from harness.plugin_generator import generate_orchestrator_plugin
from harness.renderer import TemplateRenderer

def should_generate_orchestrator_plugin(domain_content: str, platform_choice: str) -> bool:
    """Detect if orchestrator-plugin is selected and platform is Claude Code."""
    if platform_choice != "2":  # Only for Claude Code
        return False

    if not domain_content:
        return False

    # Check if orchestrator-plugin is selected (marked with [x])
    return bool(re.search(r'- \[[xX]\]\s+orchestrator-plugin', domain_content))


def parse_tool_checklists(domain_content: str) -> tuple[list[dict], list[dict]]:
    """Parses selected skills and MCPs from the ONBOARDING_DOMAIN.md content."""
    skills = []
    mcps = []
    
    if not domain_content:
        return skills, mcps
        
    # Find Skills block
    skills_match = re.search(r'## Proposed Skills\n.*?(?=##|$)', domain_content, re.DOTALL)
    if skills_match:
        for line in skills_match.group(0).split('\n'):
            if line.strip().lower().startswith('- [x]'):
                # match: - [x] name (url) [optional type comment]
                m = re.match(r'- \[[xX]\]\s+([^\(]+?)\s*\((.*?)\)(?:\s*<!--\s*type:(.*?)\s*-->)?', line.strip())
                if m:
                    skill_type = m.group(3).strip() if m.group(3) else "skill"
                    skills.append({"name": m.group(1).strip(), "url": m.group(2).strip(), "type": skill_type})
                    
    # Find MCPs block
    mcps_match = re.search(r'## Proposed MCP Tools\n.*?(?=##|$)', domain_content, re.DOTALL)
    if mcps_match:
        for line in mcps_match.group(0).split('\n'):
            if line.strip().lower().startswith('- [x]'):
                 m = re.match(r'- \[[xX]\]\s+([^\(]+?)\s*\((.*?)\)', line.strip())
                 if m:
                     mcps.append({"name": m.group(1).strip(), "command": m.group(2).strip()})
                     
    return skills, mcps

def wait_for_user_review_and_read_domain(project_path: str) -> str:
    """Pauses execution waiting for the user, then reads the domain doc with validation."""
    doc_path = os.path.join(project_path, "ONBOARDING_DOMAIN.md")
    
    if not os.path.exists(doc_path):
        print(f"Warning: {doc_path} not found. Skipping pause.")
        return ""

    # Headless mode bypass
    if os.environ.get("HARNESS_HEADLESS") == "1":
        print("Headless mode: Skipping user review pause.")
        try:
            with open(doc_path, 'r') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading {doc_path}: {e}")
            return ""

    print(f"\n{'='*60}")
    print(f"ACTION REQUIRED: Please open {doc_path}")
    print("Fill in the domain invariants and ubiquitous language.")
    print(f"{'='*60}\n")
    
    while True:
        input("Press ENTER when you have saved your changes to ONBOARDING_DOMAIN.md...")
        
        try:
            with open(doc_path, 'r') as f:
                content = f.read()
                if "[USER INPUT REQUIRED]" in content:
                    print("\033[91mWARNING: You still have '[USER INPUT REQUIRED]' placeholders in your document.\033[0m")
                    choice = input("Are you sure you want to proceed? (y/N): ").strip().lower()
                    if choice in ['y', 'yes']:
                        return content
                    else:
                        continue
                return content
        except Exception as e:
            print(f"Error reading {doc_path}: {e}")
            return ""

def process_includes(content: str, current_file_path: str, target_root: Path, tool_replacements: dict, target_dir_name: str, visited: set = None) -> str:
    """Recursively resolves @path includes at the start of lines, applying placeholders."""
    if visited is None:
        visited = set()
        
    lines = content.splitlines()
    new_lines = []
    
    for line in lines:
        if line.strip().startswith("@") and not line.strip().startswith("@ "):
            include_path_str = line.strip()[1:].strip()
            
            # Resolve the path relative to the current file
            current_dir = os.path.dirname(current_file_path)
            include_path = Path(os.path.normpath(os.path.join(current_dir, include_path_str)))
            
            abs_path_str = str(include_path.absolute())
            if abs_path_str in visited:
                print(f"Warning: Circular include detected for {include_path}")
                new_lines.append(line)
                continue
                
            if include_path.exists() and include_path.is_file():
                try:
                    with open(include_path, "r") as f:
                        include_content = f.read()
                        
                    # Apply placeholders and tool mappings to the included content FIRST
                    include_content = include_content.replace(".claude", target_dir_name)
                    for old_tool, new_tool in tool_replacements.items():
                        include_content = include_content.replace(old_tool, new_tool)
                        
                    visited.add(abs_path_str)
                    # Recursively process includes in the included file
                    resolved_content = process_includes(include_content, str(include_path), target_root, tool_replacements, target_dir_name, visited)
                    visited.remove(abs_path_str)
                    new_lines.append(resolved_content)
                except Exception as e:
                    print(f"Warning: Failed to inline {include_path}: {e}")
                    new_lines.append(line)
            else:
                # If it doesn't exist, maybe it's a subagent name like @agent
                # or it hasn't been minted yet. We leave it as is if it's not a valid file.
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    return "\n".join(new_lines)

def mint_workspace(target_dir: str, selected_agents: list[dict], project_path: str, platform_choice: str, model_choice: str = None, boilerplate_dir: str = None, ddd_context: dict = None):
    """Copies boilerplate, injects styled configs, and writes setup prerequisites."""
    target_path = Path(target_dir)
    target_dir_name = target_path.name
    
    if target_path.exists():
        print(f"Warning: Target directory {target_dir} already exists. Minting may overwrite files.")
        
    # Get selected tools from the domain doc to check if plugin is selected
    domain_content_str = ddd_context.get("source", "") if ddd_context else ""
    if not domain_content_str:
        domain_doc_path = os.path.join(project_path, "ONBOARDING_DOMAIN.md")
        if os.path.exists(domain_doc_path):
            with open(domain_doc_path, "r") as f:
                domain_content_str = f.read()
    
    def ignore_patterns(dir_path, contents):
        ignored = ['.git', '__pycache__', '.DS_Store']
        return [i for i in contents if i in ignored or i.endswith('.log')]
        
    if boilerplate_dir and os.path.exists(boilerplate_dir):
        shutil.copytree(boilerplate_dir, target_path, ignore=ignore_patterns, dirs_exist_ok=True)
        
        # Tool mapping for specific platforms
        platform_map_normalized = {"1": "gemini", "2": "claude", "3": "cursor", "4": "agents", "5": "codex"}
        current_platform = platform_map_normalized.get(platform_choice, platform_choice).lower()
        
        tool_replacements = {}
        renderer_context = {
            "HARNESS_DIR": target_dir_name,
            "SUBAGENT_SYNTAX": "@"
        }

        if current_platform == "claude":
            renderer_context["SUBAGENT_SYNTAX"] = "Task tool: "
            tool_replacements = {
                "- read_file": "- Read",
                "- grep_search": "- Grep",
                "- replace": "- Edit",
                "- write_file": "- Write",
                "- run_shell_command": "- Bash",
                "- glob": "- Glob",
                "read_file": "Read",
                "grep_search": "Grep",
                "replace": "Edit",
                "write_file": "Write",
                "run_shell_command": "Bash",
                "glob": "Glob"
            }
        elif current_platform == "codex":
            renderer_context["SUBAGENT_SYNTAX"] = "Hand off to "
        else:
            renderer_context["SUBAGENT_SYNTAX"] = "@"

        renderer = TemplateRenderer()

        # Step 1: Apply placeholders and tool mappings to all files
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith((".md", ".json", ".yaml", ".yml")):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r") as f:
                            content = f.read()
                            
                        new_content = content
                        
                        # Handle old-style placeholders for backward compatibility or direct strings
                        new_content = new_content.replace(".claude", target_dir_name)
                        if "@boilerplate-agent" in new_content:
                            new_content = new_content.replace("@boilerplate-agent", target_dir_name)
                            
                        # Apply Template Rendering
                        try:
                            new_content = renderer.render_string(new_content, renderer_context)
                        except Exception as render_err:
                            # If rendering fails (e.g. because of random <!--$ in some file), just log and move on
                            pass
                            
                        # Apply specialized agents injection specifically for dispatch_rules.md
                        if file == "dispatch_rules.md" and selected_agents:
                            agent_names = [agent['name'] for agent in selected_agents]
                            agents_str = ", ".join([f"`@{name}`" for name in agent_names])
                            injection = f"\n- **Domain Specific Routing**: If the task involves domain-specific areas similar to the domains defined by the newly minted specialized agents ({agents_str}), you MUST route to those agents. Refer to their markdown files in the agents directory for their specific mandates.\n"
                            
                            # Inject right before the Negative Routing Rules section
                            if "**Negative Routing Rules" in new_content:
                                new_content = new_content.replace("**Negative Routing Rules", injection + "**Negative Routing Rules")

                            
                        # Apply tool mappings if any
                        for old_tool, new_tool in tool_replacements.items():
                            new_content = new_content.replace(old_tool, new_tool)
                            
                        if new_content != content:
                            with open(filepath, "w") as f:
                                f.write(new_content)
                    except Exception as e:
                        print(f"Warning: Failed to process placeholders in {filepath}: {e}")

        # Step 2: Process @ includes (Inlining)
        # Now that all files have placeholders resolved, it's safe to inline them
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith((".md", ".json", ".yaml", ".yml")):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r") as f:
                            content = f.read()
                            
                        new_content = process_includes(content, filepath, target_path, tool_replacements, target_dir_name)
                            
                        if new_content != content:
                            with open(filepath, "w") as f:
                                f.write(new_content)
                    except Exception as e:
                        print(f"Warning: Failed to process includes in {filepath}: {e}")

        # --- Ghost Injection for implementer.md ---
        context_file = os.path.join(project_path, "docs", "domain", "CONTEXT.md")
        invariants_text = ""
        if not os.path.exists(context_file):
            os.makedirs(os.path.dirname(context_file), exist_ok=True)
            with open(context_file, "w") as f:
                f.write("# Project Context\n\n## Purpose\n\n## Ubiquitous Language\n\n## Strict Invariants\n")
        
        try:
            with open(context_file, "r") as f:
                c_text = f.read()
                if "## Strict Invariants" in c_text:
                    invariants_text = c_text.split("## Strict Invariants")[1].strip()
        except Exception as e:
            print(f"Warning: Failed to read CONTEXT.md for Ghost Injection: {e}")
        
        if invariants_text:
            implementer_path = target_path / "agents" / "implementer.md"
            if implementer_path.exists():
                with open(implementer_path, "a") as f:
                    f.write("\n\n### STRICT INVARIANTS (Ghost Injection)\n" + invariants_text)
                    
        # --- End Ghost Injection ---
    else:
        print("Error: Boilerplate directory not found.")
        return

    # Generate specialized setup_harness.sh (Prerequisites)
    # Generate Segregated Setup Scripts
    project_root = Path(project_path)
    
    # Normalize platform choice
    platform_map = {
        "1": "gemini",
        "2": "claude",
        "3": "cursor",
        "4": "agents",
        "5": "codex"
    }
    active_platform = platform_map.get(platform_choice, platform_choice).lower()

    # Get selected tools from the domain doc
    domain_content_str = ddd_context.get("source", "") if ddd_context else ""
    if not domain_content_str:
        domain_doc_path = os.path.join(project_path, "ONBOARDING_DOMAIN.md")
        if os.path.exists(domain_doc_path):
            with open(domain_doc_path, "r") as f:
                domain_content_str = f.read()
    selected_skills, selected_mcps = parse_tool_checklists(domain_content_str)

    import shlex
    escaped_project_path = os.path.abspath(project_path)
    quoted_project_path = shlex.quote(escaped_project_path)
    
    # Tool installation snippets
    skill_installs = ""
    mcp_installs = ""
    
    if active_platform == "gemini":
        for s in selected_skills:
            if s.get('type') == 'extension':
                skill_installs += f"    gemini extensions install {s['url']} || true\n"
        for m in selected_mcps:
            cmd = m["command"]
            if " " in cmd:
                cmd = f'bash -c {shlex.quote(cmd)}'
            mcp_installs += f'    gemini mcp add {m["name"]} {cmd} || true\n'
    elif active_platform == "claude":
        for s in selected_skills:
            if s.get('type') == 'extension':
                 skill_installs += f'echo "  /plugin install {s["name"]}@{s["url"]} --project"\n'
        # We handle MCP installs below by generating .mcp.json directly
    elif active_platform == "cursor":
        for s in selected_skills:
            skill_installs += f'echo "  /add-plugin {s["name"]} ({s["url"]})"\n'

    import json
    mcp_config_dict = {
        "mcpServers": {
            "codegraph": {
                "command": "npx",
                "args": ["-y", "@colbymchenry/codegraph", "serve", "--mcp"]
            }
        }
    }
    if active_platform == "claude":
        for m in selected_mcps:
            parts = m["command"].split(" ")
            mcp_config_dict["mcpServers"][m["name"]] = {
                "command": parts[0],
                "args": parts[1:]
            }
    
    mcp_json_str = json.dumps(mcp_config_dict, indent=2)

    scripts_to_generate = {
        "gemini": f"""#!/usr/bin/env bash
set -e
cd {quoted_project_path}
if command -v gemini &> /dev/null; then
{skill_installs}
    
    echo "Ensuring CodeGraph is build..."
    npx -y @colbymchenry/codegraph init --index || true

    echo "Adding codegraph to Gemini CLI project MCP configuration..."
    gemini mcp add codegraph npx -y @colbymchenry/codegraph serve --mcp || true
{mcp_installs}
else
    echo "Warning: gemini command not found."
fi

echo "To activate it, run Gemini from the project root and use '/mcp reload'."
""",
        "claude": f"""#!/usr/bin/env bash
set -e
cd {quoted_project_path}
echo "=== Setting up Superpowers for Claude Code ==="
PLUGIN_READY=0
CODEGRAPH_READY=0

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ACTION REQUIRED] python3 is required but was not found."
    exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 8):
    raise SystemExit("[ACTION REQUIRED] Python 3.8+ is required.")
print(f"Python runtime OK: {{sys.version.split()[0]}}")
PY

echo "Registering codegraph with Claude Code..."
if command -v claude >/dev/null 2>&1; then
    claude mcp add --scope project codegraph "npx @colbymchenry/codegraph serve --mcp" || echo "Warning: Failed to add codegraph to Claude MCP"
else
    echo "Warning: 'claude' CLI not found. Run 'claude mcp add --scope project codegraph \"npx @colbymchenry/codegraph serve --mcp\"' manually."
fi

echo "Installing plugin dependencies..."
if [ -f ".claude/plugin-generated/pyproject.toml" ]; then
    pip install -e ".claude/plugin-generated" --quiet || echo "Warning: Failed to install plugin dependencies. Ensure you have pip installed and are in a virtual environment."
fi

echo "Running generated plugin smoke test..."
python3 - <<'PY'
import importlib
import json
import sys
import subprocess
from pathlib import Path

plugin = Path(".claude/plugin-generated")
required = [
    plugin / ".claude-plugin" / "plugin.json",
    plugin / "src" / "dispatcher.py",
    plugin / "src" / "hooks" / "prompt_interceptor.py",
    plugin / "src" / "hooks" / "pre_tool_guard.py",
    plugin / "src" / "hooks" / "post_tool_monitor.py",
    plugin / "src" / "hooks" / "precompact_monitor.py",
    plugin / "src" / "hooks" / "stop_monitor.py",
    plugin / "config" / "ddd-context.json",
    plugin / "agents",
    plugin / "skills",
    plugin / "scripts" / "gatekeeper.py",
    plugin / "src" / "hook_validator.py",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    print("[ACTION REQUIRED] Generated plugin payload is incomplete:")
    for path in missing:
        print(f"  - {{path}}")
    raise SystemExit(1)

sys.path.insert(0, str(plugin))
importlib.import_module("src.dispatcher")
json.loads((plugin / "config" / "ddd-context.json").read_text())
print("Plugin payload structure OK.")

print("Running hook validation...")
validator = plugin / "src" / "hook_validator.py"
result = subprocess.run([sys.executable, str(validator)], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)
    print("[ACTION REQUIRED] Hook validation failed.")
    raise SystemExit(1)
print("Hook validation OK.")
PY

echo "To install Skills for Claude Code workspace-wide, run these commands inside the Claude Code interface:"
{skill_installs}

# Orchestrator Plugin Installation
if [ -d ".claude/plugin-generated" ]; then
    echo "Checking for non-interactive Claude Code plugin install support..."
    if command -v claude >/dev/null 2>&1 && claude plugin --help >/dev/null 2>&1; then
        if claude plugin marketplace add "$PWD/.claude/plugin-generated" --scope project && claude plugin install orchestrator-plugin@local-orchestrator-marketplace --scope project; then
            PLUGIN_READY=1
            echo "Orchestrator plugin installed automatically."
        else
            echo "[ACTION REQUIRED] Automatic plugin installation failed."
        fi
    else
        echo "[ACTION REQUIRED] Claude Code plugin CLI automation was not detected."
    fi

    if [ "$PLUGIN_READY" != "1" ]; then
        echo "[ACTION REQUIRED] Open Claude Code in this repo and run:"
        echo "  /plugin marketplace add \"\$PWD/.claude/plugin-generated\" --scope project"
        echo "  /plugin install orchestrator-plugin@local-orchestrator-marketplace --scope project"
        echo "Restart or reload Claude Code if hooks/tools do not appear immediately."
    fi
fi

# MCP Configuration for Claude via .mcp.json
echo "Ensuring CodeGraph is built..."
npx -y @colbymchenry/codegraph init --index || true

echo "Generating repo-level .mcp.json..."
cat << 'MCPJSON' > .mcp.json
{mcp_json_str}
MCPJSON
CODEGRAPH_READY=1
echo "✅ MCP servers configured in .mcp.json"


python3 - <<PY
import json
import os
import sys
import time
from pathlib import Path

config = Path(".claude/plugin-generated/config")
config.mkdir(parents=True, exist_ok=True)
state_file = config / ".harness_state.json"
tmp_file = config / ".harness_state.tmp.json"
lock_dir = config / ".harness_state.json.lock"

start = time.time()
while True:
    try:
        lock_dir.mkdir()
        break
    except FileExistsError:
        if time.time() - start > 5:
            raise SystemExit("[ACTION REQUIRED] Could not acquire harness state lock.")
        time.sleep(0.05)

try:
    state = {{}}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except json.JSONDecodeError:
            state = {{}}
    state.update({{
        "setup_complete": True,
        "python_version": sys.version.split()[0],
        "codegraph_ready": os.environ.get("CODEGRAPH_READY", "$CODEGRAPH_READY") == "1",
        "plugin_install_manual_steps_printed": os.environ.get("PLUGIN_READY", "$PLUGIN_READY") != "1",
        "strict_enforcement_enabled": os.environ.get("CODEGRAPH_READY", "$CODEGRAPH_READY") == "1",
    }})
    tmp_file.write_text(json.dumps(state, indent=2))
    os.replace(tmp_file, state_file)
finally:
    try:
        lock_dir.rmdir()
    except OSError:
        pass
PY

if [ "$CODEGRAPH_READY" = "1" ]; then
    echo "Harness setup complete. Strict enforcement is ready after plugin activation."
else
    echo "[ACTION REQUIRED] Harness setup did not complete CodeGraph readiness; strict enforcement remains disabled."
fi
""",
        "cursor": f"""#!/usr/bin/env bash
set -e
cd {quoted_project_path}
echo "=== Setting up Superpowers for Cursor ==="
echo "To install Superpowers and Skills for Cursor, run these commands inside the Cursor Agent chat:"
echo "  /add-plugin superpowers"
echo "  /add-plugin mattpocock/skills"
{skill_installs}
""",
        "codex": f"""#!/usr/bin/env bash
set -e
cd {quoted_project_path}
echo "=== Setting up Superpowers for Codex ==="
echo "Please add codegraph MCP to your Codex configuration."
"""
    }

    # Write setup script
    if active_platform in scripts_to_generate:
        script_content = scripts_to_generate[active_platform]
        
        script_dir = project_root / f".{active_platform}" / "scripts"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_path = script_dir / "setup_harness.sh"
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
    
    # Generate Platform Rules Pointers IN THE ROOT DIRECTORY
    harness_prefix = f".{active_platform}" if active_platform in ["gemini", "claude", "cursor", "codex"] else target_dir_name
    pointer_content = f"""# Agentic Harness
    
Please read `{harness_prefix}/AGENTS.md` for core repository instructions and routing rules.
The Orchestrator agent and core rules are located in `{harness_prefix}/orchestrator.md`.
Run `sh {harness_prefix}/scripts/setup_harness.sh` after `harness-wf init` to complete local tool, MCP, and plugin readiness checks.
"""

    if active_platform in ["cursor", "codex"]:
        pointer_content += "\n## Available Agent Skills\n"
        pointer_content += "To activate a skill, you MUST use your file reading tool to read its instructions into your context before beginning work.\n\n"
        
        has_sp = any(s.get('name') == 'using-superpowers' for s in selected_skills)
        if not has_sp:
            pointer_content += f"- **using-superpowers**: `{harness_prefix}/skills/using-superpowers/SKILL.md`\n"
            
        for s in selected_skills:
            if s.get('type') != 'extension':
                pointer_content += f"- **{s['name']}**: `{harness_prefix}/skills/{s['name']}/SKILL.md`\n"

    # Map the platform to its specific pointer files
    pointer_files_map = {
        "gemini": ["GEMINI.md"],
        "claude": ["CLAUDE.md"],
        "cursor": [".cursorrules"],
        "codex": ["CODEX.md"],
        "agents": []
    }
    
    files_to_generate = pointer_files_map.get(active_platform, [])
    
    for rules_file in files_to_generate:
        with open(project_root / rules_file, "w") as f:
            f.write(pointer_content)
            
    if active_platform == "cursor":
        copilot_dir = project_root / ".github"
        copilot_dir.mkdir(exist_ok=True)
        with open(copilot_dir / "copilot-instructions.md", "w") as f:
            f.write(pointer_content)
        
    print(f"\nHarness files generated. Next: run `sh .{active_platform}/scripts/setup_harness.sh` from the project root to complete local setup.")

    # Create an MCP config for CodeGraph
    mcp_config = {
        "mcpServers": {
            "codegraph": {
                "command": "npx",
                "args": ["-y", "@colbymchenry/codegraph", "serve", "--mcp"]
            }
        }
    }
    
    # Generate mcp.json as a fallback/reference configuration
    mcp_path = target_path / "mcp.json"
    with open(mcp_path, 'w') as f:
         json.dump(mcp_config, f, indent=2)
         
    # Helper to generate a valid URL-safe slug
    def to_slug(text):
        # 1. Handle CamelCase (Insert hyphens between lower-to-upper transitions)
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', text)
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()
        # 2. Replace any non-alphanumeric character (except hyphens) with a hyphen
        s3 = re.sub(r'[^a-z0-9]+', '-', s2)
        # 3. Clean up multiple hyphens and leading/trailing
        return re.sub(r'-+', '-', s3).strip('-')

    # Generate Specialized Agents
    if active_platform == "codex":
        agents_md_content = "# Codex Agents Manifest\n\n"
        for agent in selected_agents:
            safe_name = to_slug(agent["name"])
            
            zone = agent.get("zone", "Core").lower()
            if zone in ["infra", "logic"]:
                sandbox_mode = "workspace-write"
            else:
                sandbox_mode = "read-only"
                
            model_val = model_choice if model_choice else "claude-3-5-sonnet-20241022"
            
            yaml_block = f"```yaml\ndescription: \"{agent['role']}\"\nmodel: \"{model_val}\"\nsandbox_mode: \"{sandbox_mode}\"\nmcp_servers: [\"codegraph\"]\n```"
            
            system_prompt = agent.get("system_prompt", f"# {agent['name']}\n\n{agent['role']}")
            
            
            agents_md_content += f"## {safe_name}\n{yaml_block}\n\n{system_prompt}\n\n"
            
        agents_file_path = target_path / "AGENTS.md"
        
        # Apply placeholders and includes
        agents_md_content = agents_md_content.replace(".claude", target_dir_name)
        agents_md_content = process_includes(agents_md_content, str(agents_file_path), target_path, tool_replacements, target_dir_name)
        
        with open(agents_file_path, 'w') as f:
            f.write(agents_md_content)
    else:
        for agent in selected_agents:
            safe_name = to_slug(agent["name"])
            
            agent_dir_path = target_path / "agents"
            agent_dir_path.mkdir(parents=True, exist_ok=True)
            agent_file_path = agent_dir_path / f"{safe_name}.md" 
            
            # Select base tools based on platform
            if active_platform == "claude":
                tools_list = """  - Read
  - Grep
  - Edit
  - Bash
  - Glob
  - mcp_codegraph_codegraph_search
  - mcp_codegraph_codegraph_node
  - mcp_codegraph_codegraph_context
  - mcp_codegraph_codegraph_callers
  - mcp_codegraph_codegraph_impact"""
            else:
                tools_list = """  - read_file
  - grep_search
  - replace
  - run_shell_command
  - glob
  - mcp_codegraph_codegraph_search
  - mcp_codegraph_codegraph_node
  - mcp_codegraph_codegraph_context
  - mcp_codegraph_codegraph_callers
  - mcp_codegraph_codegraph_impact"""
            
            frontmatter = f"""---
name: {safe_name}
description: {agent["role"]}
tools:
{tools_list}
---
"""
            system_prompt = agent.get("system_prompt", f"# {agent['name']}\n\n{agent['role']}")
            

            # Determine the correct include syntax based on platform
            include_pointer = ""
            if active_platform not in ["gemini", "claude", "cursor", "codex", "agents"]:
                # Fallback for cursor/agents where include syntax might not be natively supported
                include_pointer = "<!-- Core Mandates should be read from ../rules/base_mandate.md -->\n\n"

            final_content = frontmatter + include_pointer + system_prompt + "\n"
            
            # Final post-processing for placeholders and includes
            final_content = final_content.replace(".claude", target_dir_name)
            final_content = process_includes(final_content, str(agent_file_path), target_path, tool_replacements, target_dir_name)
            
            with open(agent_file_path, 'w') as f:
                f.write(final_content)
            
    print(f"Successfully minted workspace at {target_dir}")
    print("\nNext Steps:")
    print(f"1. ./{target_dir_name}/scripts/setup_harness.sh (Run from your project root, do NOT cd into {target_dir})")
    print("2. Activate your environment and Launch AI")

def synthesize_domain_sme_agent(target_dir: str, domain_content: str, harness_folder_name: str, platform_choice: str = "1", model_choice: str = None):
    """Generates the domain SME agent deterministically based on the filled doc."""
    if not domain_content:
        return None

    # Extract proposed name, fallback to domain-sme
    agent_name = "domain-sme"
    # Robust regex for: **Proposed Agent Name:** `@name` or Proposed Agent Name: @name
    name_match = re.search(r'Proposed Agent Name:.*?\s*`?@([a-zA-Z0-9_-]+)`?', domain_content, re.IGNORECASE)
    if name_match:
        agent_name = name_match.group(1).lower()
        
    # Extract sections using regex
    invariants = "None provided."
    glossary = "None provided."
    
    try:
        # Domain Invariants
        inv_pattern = re.compile(r'Domain Invariants.*?\n(.*?)(?=Ubiquitous Language|## Proposed Skills|## Proposed MCP Tools|$)', re.DOTALL | re.IGNORECASE)
        inv_match = inv_pattern.search(domain_content)
        if inv_match:
            raw_inv = inv_match.group(1).strip()
            # Clean up potential instruction text in parentheses or bold colons
            raw_inv = re.sub(r'\(.*?\)', '', raw_inv)
            invariants = raw_inv.replace("**:**", "").replace(":", "").strip()

        # Ubiquitous Language
        glo_pattern = re.compile(r'Ubiquitous Language.*?\n(.*?)(?=## Proposed Skills|## Proposed MCP Tools|$)', re.DOTALL | re.IGNORECASE)
        glo_match = glo_pattern.search(domain_content)
        if glo_match:
            raw_glo = glo_match.group(1).strip()
            # Clean up potential instruction text in parentheses or bold colons
            raw_glo = re.sub(r'\(.*?\)', '', raw_glo)
            glossary = raw_glo.replace("**:**", "").replace(":", "").strip()
            
    except Exception as e:
        print(f"Warning: Failed to parse domain doc sections: {e}")

    agent_markdown = f"""# Role: Domain Subject Matter Expert
You are the definitive authority on the business logic, ubiquitous language, and architectural constraints.

# Core Mandates
1. **Security & System Integrity:** Never log, print, or commit secrets.
2. **Context Efficiency:** Your context window is isolated.
3. **No Chitchat:** Focus exclusively on intent and technical rationale.

# Domain-Specific Invariants (The MOAT)
<invariants>
{invariants}
</invariants>

# Ubiquitous Language (Glossary)
<glossary>
{glossary}
</glossary>

# Operational Instructions
1. **Audit:** Review proposed plans against your <invariants>. 
2. **Correct:** Identify any misuse of terms.
3. **Reject:** Reject plans that violate domain rules. Provide architectural corrections, NOT implementation code.
"""

    if platform_choice == "5":
        try:
            agents_file_path = os.path.join(target_dir, harness_folder_name, "AGENTS.md")
            if os.path.exists(agents_file_path):
                with open(agents_file_path, "r") as f:
                    existing_content = f.read()
            else:
                existing_content = "# Codex Agents Manifest\n\n"
            
            model_val = model_choice if model_choice else "claude-3-5-sonnet-20241022"
            
            yaml_block = f"""```yaml
description: "Subject Matter Expert and Guardian. Consult this agent before modifying core logic."
model: "{model_val}"
sandbox_mode: "read-only"
mcp_servers: ["codegraph"]
```"""
            
            sme_section = f"""
## {agent_name}
{yaml_block}

{agent_markdown}
"""
            new_content = existing_content.rstrip() + "\n\n" + sme_section.strip() + "\n"
            # Apply placeholders as Codex AGENTS.md might need them (consistent with mint_workspace)
            new_content = new_content.replace(".claude", harness_folder_name)
            
            with open(agents_file_path, "w") as f:
                f.write(new_content)
            
            print(f"[HARNESS] Appended {agent_name} to {agents_file_path}")
            return agent_name
        except Exception as e:
            print(f"Error appending to AGENTS.md for Codex: {e}")
            return None
    else:
        full_agent_markdown = f"""---
name: {agent_name}
description: Subject Matter Expert and Guardian. Consult this agent before modifying core logic.
---
{agent_markdown}
"""
        try:
            agents_dir = os.path.join(target_dir, harness_folder_name, "agents")
            os.makedirs(agents_dir, exist_ok=True)
            
            file_path = os.path.join(agents_dir, f"{agent_name}.md")
            with open(file_path, "w") as f:
                f.write(full_agent_markdown.strip() + "\n")
                
            print(f"[HARNESS] Synthesized {agent_name} at {file_path}")
            return agent_name
            
        except Exception as e:
            print(f"Error synthesizing domain agent: {e}")
            return None

def patch_orchestrator_rules(target_dir: str, agent_name: str, harness_folder_name: str, target_syntax: str = "@"):
    """Injects the new Domain SME into the Orchestrator's dispatch rules."""
    if not agent_name:
        return

    rules_path = os.path.join(target_dir, harness_folder_name, "rules", "dispatch_rules.md")
    if not os.path.exists(rules_path):
         # If rules don't exist yet, try orchestrator.md directly
         rules_path = os.path.join(target_dir, harness_folder_name, "orchestrator.md")
         if not os.path.exists(rules_path):
             print("Warning: Could not find rules to patch Domain SME.")
             return
    with open(rules_path, "r") as f:
        content = f.read()
        
    # Construct the patch
    planner_ref = f"{target_syntax}planner"
    sme_ref = f"{target_syntax}{agent_name}"
    
    sme_rule = f"""
- **Domain SME Gateway**: If a task touches core logic or invariants, you MUST first dispatch the `{sme_ref}` to generate a "Domain Constraints Brief" before allowing the `{planner_ref}` to create the implementation plan.
"""
    
    # Try to insert after the Hierarchy section or at the top of Tool Delegation
    if "</orchestration_hierarchy>" in content:
        parts = content.split("</orchestration_hierarchy>")
        new_content = parts[0] + "\n" + sme_rule + "\n</orchestration_hierarchy>" + parts[1]
    elif "### DOMAIN DRIVEN DESIGN (DDD):" in content:
        parts = content.split("### DOMAIN DRIVEN DESIGN (DDD):")
        new_content = parts[0] + "### Domain SME Gateway\n" + sme_rule + "\n\n### DOMAIN DRIVEN DESIGN (DDD):" + parts[1]
    else:
        # Fallback append to bottom
        new_content = content + "\n\n### Domain SME Gateway\n" + sme_rule
        
    with open(rules_path, "w") as f:
        f.write(new_content)
        
    print(f"[HARNESS] Patched Orchestrator rules with {sme_ref}")

def install_workspace_tools(target_dir: str, harness_folder_name: str, skills: list[dict], mcps: list[dict]):
    """Downloads remote skills and configures MCPs locally for the workspace."""
    harness_dir = os.path.join(target_dir, harness_folder_name)
    
    # Defensive copy and normalize
    skills_to_install = list(skills) if skills else []
    
    # Ensure the localized using-harness-superpowers is registered if needed
    has_superpowers = any(s.get('name') == 'using-harness-superpowers' for s in skills_to_install)
    if not has_superpowers:
        # We don't download it from github anymore, it's baked into the boilerplate!
        # Just ensure it's recorded in the skills metadata if necessary
        pass
    
    # Install Skills (using the new list)
    if skills_to_install:
        skills_json_path = os.path.join(harness_dir, "skills.json")
        skills_data = {"skills": {}}
        if os.path.exists(skills_json_path):
            try:
                with open(skills_json_path, "r") as f:
                    skills_data = json.load(f)
            except json.JSONDecodeError:
                pass

        for skill in skills_to_install:
            if skill.get('type') == 'extension':
                print(f"[HARNESS] Skipping download for extension: {skill['name']}")
                continue
                
            try:
                print(f"[HARNESS] Downloading skill: {skill['name']}...")
                req = urllib.request.Request(skill['url'], headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    content = response.read().decode('utf-8')
                    
                skill_dir = os.path.join(harness_dir, "skills", skill['name'])
                os.makedirs(skill_dir, exist_ok=True)
                skill_file = os.path.join(skill_dir, "SKILL.md")
                with open(skill_file, "w") as f:
                    f.write(content)
                    
                # Update skills.json with LOCAL path relative to workspace
                skills_data["skills"][skill['name']] = {"path": f"skills/{skill['name']}/SKILL.md"}
            except Exception as e:
                # Local fallback check
                print(f"Network fetch failed for {skill['name']}: {e}. Checking local boilerplate fallback...")
                import shutil
                # We need to reach the boilerplate directory. We can guess it's roughly 2 dirs up from harness_dir
                from harness.utils import get_boilerplate_dir
                local_skill_path = get_boilerplate_dir() / "skills" / skill['name'] / "SKILL.md"
                if local_skill_path.exists():
                    skill_dir = os.path.join(harness_dir, "skills", skill['name'])
                    os.makedirs(skill_dir, exist_ok=True)
                    skill_file = os.path.join(skill_dir, "SKILL.md")
                    shutil.copyfile(local_skill_path, skill_file)
                    print(f"[HARNESS] Successfully copied local fallback for skill: {skill['name']}")
                    skills_data["skills"][skill['name']] = {"path": f"skills/{skill['name']}/SKILL.md"}
                else:
                    print(f"Failed to install skill {skill['name']} (no local fallback found at {local_skill_path})")
                
        with open(skills_json_path, "w") as f:
             json.dump(skills_data, f, indent=2)
    if mcps:
        mcp_json_path = os.path.join(harness_dir, "mcp.json")
        mcp_data = {"mcpServers": {}}
        if os.path.exists(mcp_json_path):
             try:
                 with open(mcp_json_path, "r") as f:
                     mcp_data = json.load(f)
             except json.JSONDecodeError:
                 pass
                 
        for mcp in mcps:
            print(f"[HARNESS] Configuring MCP: {mcp['name']}...")
            import shlex
            parts = shlex.split(mcp['command'])
            if parts:
                mcp_data["mcpServers"][mcp['name']] = {
                    "command": parts[0],
                    "args": parts[1:]
                }

        with open(mcp_json_path, "w") as f:
             json.dump(mcp_data, f, indent=2)
