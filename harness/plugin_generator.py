"""Plugin generator for orchestrator-based Claude Code integration."""
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional


def generate_plugin_manifest(
    target_dir: str,
    project_name: str,
    plugin_version: str = "1.0.0",
    skills_dir: Optional[Path] = None
) -> str:
    """Generate plugin.json manifest for the orchestrator plugin.

    Args:
        target_dir: Directory to generate plugin in (e.g., .claude/plugin-generated)
        project_name: Name of the project (for display)
        plugin_version: Version of the plugin
        skills_dir: Optional path to skills directory to register dynamic tools

    Returns:
        Path to the generated plugin.json
    """
    plugin_dir = Path(target_dir)
    claude_plugin_dir = plugin_dir / ".claude-plugin"
    claude_plugin_dir.mkdir(parents=True, exist_ok=True)

    tools = [
        {
            "name": "Skill",
            "description": "Invoke a specialized agent skill by name",
            "entry_point": "src/tools.py:invoke_skill",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the skill to invoke"
                    }
                },
                "required": ["name"]
            }
        },
        {
            "name": "Task",
            "description": "Invoke a subagent to perform a specific task",
            "entry_point": "src/tools.py:invoke_task",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Name of the subagent to invoke"
                    },
                    "prompt": {
                        "type": "string",
                        "description": "The prompt or instruction for the subagent"
                    }
                },
                "required": ["agent_name", "prompt"]
            }
        }
    ]

    if skills_dir and skills_dir.exists():
        # Get top 10 skills
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
        
        core_skills = ["harness-test-driven-development", "diagnose", "harness-writing-plans"]
        def sort_key(d):
            try:
                priority = core_skills.index(d.name)
            except ValueError:
                priority = len(core_skills)
            return (priority, d.name)

        # Sort for determinism
        skill_dirs.sort(key=sort_key)
        top_skills = skill_dirs[:10]

        for skill_dir in top_skills:
            skill_name = skill_dir.name
            safe_name = skill_name.replace('-', '_')
            tools.append({
                "name": f"skill_{safe_name}",
                "description": f"Invoke the specialized '{skill_name}' skill directly.",
                "entry_point": f"src/tools.py:invoke_specific_skill_{safe_name}",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            })

    manifest = {
        "name": "orchestrator-plugin",
        "description": f"Auto-generated orchestrator plugin for {project_name}",
        "version": plugin_version,
        "author": {
            "name": "Harness Plugin Generator"
        },
        "entry_point": "src/orchestrator_plugin.py",
        "requirements": [
            "pydantic>=2.0",
            "typing_extensions"
        ],
        "hooks": {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "PYTHONPATH=.claude/plugin-generated python3 -m src.hooks.prompt_interceptor"
                        }
                    ]
                }
            ],
            "PreToolUse": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "PYTHONPATH=.claude/plugin-generated python3 -m src.hooks.pre_tool_guard"
                        }
                    ]
                }
            ],
            "PostToolUse": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "PYTHONPATH=.claude/plugin-generated python3 -m src.hooks.post_tool_monitor"
                        }
                    ]
                }
            ],
            "PreCompact": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "PYTHONPATH=.claude/plugin-generated python3 -m src.hooks.precompact_monitor"
                        }
                    ]
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "PYTHONPATH=.claude/plugin-generated python3 -m src.hooks.stop_monitor"
                        }
                    ]
                }
            ]
        },
        "tools": tools
    }

    manifest_path = claude_plugin_dir / "plugin.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
        
    marketplace = {
        "name": "local-orchestrator-marketplace",
        "owner": {
            "name": "Local Project"
        },
        "plugins": [
            {
                "name": "orchestrator-plugin",
                "version": plugin_version,
                "source": "./"
            }
        ]
    }
    
    marketplace_path = claude_plugin_dir / "marketplace.json"
    with open(marketplace_path, 'w') as f:
        json.dump(marketplace, f, indent=2)

    return str(manifest_path)


def export_orchestrator_config(orchestrator_path: Path, config_dir: Path) -> str:
    """Export orchestrator configuration from .md to JSON format.

    Args:
        orchestrator_path: Path to orchestrator.md
        config_dir: Directory to export config to

    Returns:
        Path to exported orchestrator.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    # Read orchestrator.md
    with open(orchestrator_path, 'r') as f:
        content = f.read()

    # Create a basic JSON with metadata
    orchestrator_json = {
        "source": str(orchestrator_path),
        "content": content,
        "generated_at": "auto"
    }

    export_path = config_dir / "orchestrator.json"
    with open(export_path, 'w') as f:
        json.dump(orchestrator_json, f, indent=2)

    return str(export_path)


def export_agents_config(agents_dir: Path, config_dir: Path) -> str:
    """Export agent definitions from agents/ directory to agents.json.

    Args:
        agents_dir: Path to agents directory
        config_dir: Directory to export config to

    Returns:
        Path to exported agents.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    agents = {}
    if agents_dir.exists():
        for agent_file in agents_dir.glob("*.md"):
            agent_name = agent_file.stem
            with open(agent_file, 'r') as f:
                agents[agent_name] = {
                    "path": str(agent_file),
                    "source": f.read()
                }

    agents_json = {
        "agents": agents,
        "count": len(agents)
    }

    export_path = config_dir / "agents.json"
    with open(export_path, 'w') as f:
        json.dump(agents_json, f, indent=2)

    return str(export_path)


def export_ddd_context(context_path: Path, config_dir: Path) -> str:
    """Export DDD context from CONTEXT.md to ddd-context.json.

    Args:
        context_path: Path to docs/domain/CONTEXT.md
        config_dir: Directory to export config to

    Returns:
        Path to exported ddd-context.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    ddd_context = {
        "purpose": "",
        "ubiquitous_language": {},
        "strict_invariants": []
    }

    if context_path.exists():
        with open(context_path, 'r') as f:
            content = f.read()
        ddd_context["source"] = content

    export_path = config_dir / "ddd-context.json"
    with open(export_path, 'w') as f:
        json.dump(ddd_context, f, indent=2)

    return str(export_path)


def export_rules_config(rules_dir: Path, config_dir: Path) -> str:
    """Export project mandates/rules to rules.json.

    Args:
        rules_dir: Path to rules/ directory
        config_dir: Directory to export config to

    Returns:
        Path to exported rules.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)

    rules = {}
    if rules_dir.exists():
        for rule_file in rules_dir.glob("*.md"):
            rule_name = rule_file.stem
            with open(rule_file, 'r') as f:
                rules[rule_name] = f.read()

    rules_json = {
        "rules": rules,
        "count": len(rules)
    }

    export_path = config_dir / "rules.json"
    with open(export_path, 'w') as f:
        json.dump(rules_json, f, indent=2)

    return str(export_path)


def generate_orchestrator_plugin(
    project_path: str,
    project_name: str,
    plugin_version: str = "1.0.0",
    boilerplate_dir: Optional[str] = None
) -> str:
    """Generate a complete orchestrator plugin for the project.

    Args:
        project_path: Root path of the project
        project_name: Name of the project
        plugin_version: Version of the plugin
        boilerplate_dir: Optional path to boilerplate directory

    Returns:
        Path to the generated plugin directory
    """
    try:
        project_path = Path(project_path).resolve()
        plugin_dir = project_path / ".claude" / "plugin-generated"

        # Create directory structure
        src_dir = plugin_dir / "src"
        config_dir = plugin_dir / "config"
        src_dir.mkdir(parents=True, exist_ok=True)
        config_dir.mkdir(parents=True, exist_ok=True)

        harness_dir = project_path / ".claude"
        
        # Resolve boilerplate dir
        bp_dir = Path(boilerplate_dir).resolve() if boilerplate_dir else (project_path / "boilerplate-agent").resolve()

        print(f"[HARNESS] Generating plugin at {plugin_dir}")
        print(f"[HARNESS] Using boilerplate from {bp_dir}")

        # Try boilerplate first, then fallback to harness
        agents_src = bp_dir / "agents"
        if not agents_src.exists():
            agents_src = harness_dir / "agents"
            
        skills_src = bp_dir / "skills"
        if not skills_src.exists():
            skills_src = harness_dir / "skills"

        # Generate manifest
        print(f"[HARNESS] Generating manifest...")
        generate_plugin_manifest(str(plugin_dir), project_name, plugin_version, skills_dir=skills_src)

        # Export configs
        print(f"[HARNESS] Exporting configs...")
        if harness_dir.exists():
            if (harness_dir / "orchestrator.md").exists():
                export_orchestrator_config(harness_dir / "orchestrator.md", config_dir)
            if (harness_dir / "rules").exists():
                export_rules_config(harness_dir / "rules", config_dir)

        # Deep copy agents and skills
        if agents_src.exists():
            print(f"[HARNESS] Copying agents from {agents_src}...")
            shutil.copytree(agents_src, plugin_dir / "agents", dirs_exist_ok=True)
            export_agents_config(plugin_dir / "agents", config_dir)
        else:
            print(f"[HARNESS] Warning: Agents source {agents_src} not found.")
            
        if skills_src.exists():
            print(f"[HARNESS] Copying skills from {skills_src}...")
            shutil.copytree(skills_src, plugin_dir / "skills", dirs_exist_ok=True)
        else:
            print(f"[HARNESS] Warning: Skills source {skills_src} not found.")

        scripts_src = bp_dir / "scripts"
        if scripts_src.exists():
            print(f"[HARNESS] Copying scripts from {scripts_src}...")
            shutil.copytree(scripts_src, plugin_dir / "scripts", dirs_exist_ok=True)
        else:
            print(f"[HARNESS] Warning: Scripts source {scripts_src} not found.")

        # Export DDD context
        context_path = project_path / "docs" / "domain" / "CONTEXT.md"
        print(f"[HARNESS] Exporting DDD context from {context_path}...")
        export_ddd_context(context_path, config_dir)

        # Generate plugin source files
        print(f"[HARNESS] Generating plugin sources...")
        generate_plugin_sources(src_dir, skills_dir=skills_src)
        
        # Copy dispatcher.py from harness directory
        harness_module_dir = Path(__file__).parent
        dispatcher_src = harness_module_dir / "dispatcher.py"
        if dispatcher_src.exists():
            print(f"[HARNESS] Copying dispatcher.py...")
            shutil.copy(dispatcher_src, src_dir / "dispatcher.py")
        else:
            print(f"[HARNESS] Warning: dispatcher.py not found at {dispatcher_src}")

        # Generate pyproject.toml
        generate_pyproject(plugin_dir)

        print(f"[HARNESS] Plugin generation complete.")
        return str(plugin_dir)
    except Exception as e:
        print(f"[HARNESS] ERROR during plugin generation: {e}")
        import traceback
        traceback.print_exc()
        raise


def generate_plugin_sources(src_dir: Path, skills_dir: Optional[Path] = None) -> None:
    """Generate plugin source files: orchestrator_plugin.py, dispatcher.py, interceptor.py."""
    src_dir = Path(src_dir)
    src_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py
    (src_dir / "__init__.py").write_text("")

    # Generate orchestrator_plugin.py
    orchestrator_plugin_content = '''"""
Orchestrator Plugin for Claude Code.

Enforces Hub-and-Spoke routing through the orchestrator.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Import dispatcher (generated in same package)
from .dispatcher import OrchestratorDispatcher


class OrchestratorPlugin:
    """
    Main plugin class for Claude Code.
    
    Enforces that all agent dispatching goes through the project's orchestrator.
    """
    
    def __init__(self):
        """Initialize plugin with config from .claude/plugin-generated/config."""
        plugin_dir = Path(__file__).parent.parent
        config_dir = plugin_dir / "config"
        self.dispatcher = OrchestratorDispatcher(str(config_dir))
    
    def initialize(self) -> bool:
        """
        Initialize plugin. Called when Claude Code loads the plugin.
        
        Returns:
            True if initialization successful
        """
        return True
    
    def intercept_agent_dispatch(
        self, 
        agent_name: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Intercept agent dispatch and route through orchestrator.
        
        Args:
            agent_name: Name of the agent being requested
            context: Execution context
            
        Returns:
            Dispatch result from orchestrator
        """
        # Validate rules
        if not self.dispatcher.validate_against_rules(agent_name):
            raise PermissionError(f"Agent '{agent_name}' violates project rules")
        
        # Route through orchestrator
        return self.dispatcher.dispatch_agent(agent_name, context)
        
    def read_skill(self, name: str) -> str:
        """
        Read skill markdown file.
        
        Args:
            name: Name of the skill
            
        Returns:
            Skill content or error message
        """
        # We need to find the skill either in .claude/skills or .gemini/skills or boilerplate-agent/skills
        # Get project root (we are in .claude/plugin-generated/src)
        project_root = Path(__file__).parent.parent.parent.parent
        
        # Look in possible locations
        possible_paths = [
            project_root / ".claude" / "skills" / name / "SKILL.md",
            project_root / ".gemini" / "skills" / name / "SKILL.md",
            project_root / "boilerplate-agent" / "skills" / name / "SKILL.md"
        ]
        
        for skill_path in possible_paths:
            if skill_path.exists():
                with open(skill_path, "r") as f:
                    return f.read()
                    
        return f"Error: Skill '{name}' not found."

    def dispatch_task(self, agent_name: str, prompt: str) -> str:
        """
        Dispatch a task to an agent via the tool interface.
        
        Args:
            agent_name: Name of the subagent
            prompt: Task instruction
            
        Returns:
            Result of the dispatch (subagent instructions + prompt)
        """
        try:
            # Validate and route through dispatcher logic
            dispatch_result = self.dispatcher.dispatch_agent(agent_name, {"prompt": prompt})
        except Exception as e:
            return f"Error dispatching task: {str(e)}"
            
        # Retrieve the agent's system instructions from the config
        agents = self.dispatcher.agents_config.get("agents", {})
        agent_data = agents.get(agent_name, {})
        agent_source = agent_data.get("source", "No specific agent instructions found.")
        
        # Resolve inline rule references like @../rules/base_mandate.md
        rules = self.dispatcher.rules_config.get("rules", {})
        import re
        def replace_rule(match):
            rule_filename = match.group(1)
            rule_name = rule_filename.replace('.md', '')
            if rule_name in rules:
                return f"\\n=== MANDATE: {rule_name.upper()} ===\\n" + rules[rule_name] + "\\n===========================\\n"
            return match.group(0)
            
        resolved_source = re.sub(r'@\\.\\./rules/([a-zA-Z0-9_-]+\\.md)', replace_rule, agent_source)
        
        return (
            f"[ORCHESTRATOR APPROVED TASK DISPATCH]\\n"
            f"You have been authorized to execute this task as: @{agent_name}\\n\\n"
            f"=== AGENT PERSONA / INSTRUCTIONS ===\\n"
            f"{resolved_source}\\n\\n"
            f"=== TASK TO EXECUTE ===\\n"
            f"{prompt}\\n\\n"
            f"Please execute the task following the agent persona instructions above."
        )


# Plugin singleton
_plugin_instance: Optional[OrchestratorPlugin] = None


def get_plugin() -> OrchestratorPlugin:
    """Get or create plugin instance."""
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = OrchestratorPlugin()
    return _plugin_instance


def init() -> bool:
    """
    Plugin initialization hook. Called by Claude Code on startup.
    """
    plugin = get_plugin()
    return plugin.initialize()
'''
    (src_dir / "orchestrator_plugin.py").write_text(orchestrator_plugin_content)

    # Generate interceptor.py
    interceptor_content = '''"""
Hook interception for Claude Code agent dispatch.
"""

from .orchestrator_plugin import get_plugin


def intercept_agent_dispatch(agent_name: str, context: dict) -> dict:
    """
    Hook function called when Claude Code dispatches an agent.
    
    This is registered in plugin.json hooks.agent_dispatch.
    """
    plugin = get_plugin()
    return plugin.intercept_agent_dispatch(agent_name, context)
'''
    (src_dir / "interceptor.py").write_text(interceptor_content)

    # Generate tools.py
    tools_content = '''"""
Plugin tools exposed to Claude Code.
"""

from .orchestrator_plugin import get_plugin


def invoke_skill(name: str) -> str:
    """
    Tool function to load a specialized agent skill by name.
    
    This is registered in plugin.json tools.Skill.
    """
    plugin = get_plugin()
    return plugin.read_skill(name)


def invoke_task(agent_name: str, prompt: str) -> str:
    """
    Tool function to invoke a subagent to perform a specific task.
    
    This is registered in plugin.json tools.Task.
    """
    plugin = get_plugin()
    return plugin.dispatch_task(agent_name, prompt)
'''

    if skills_dir and skills_dir.exists():
        # Get top 10 skills
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
        skill_dirs.sort(key=lambda d: d.name)
        top_skills = skill_dirs[:10]

        for skill_dir in top_skills:
            skill_name = skill_dir.name
            safe_name = skill_name.replace('-', '_')
            tools_content += f'''
def invoke_specific_skill_{safe_name}() -> str:
    """
    Tool function to load the '{skill_name}' skill directly.
    """
    return invoke_skill("{skill_name}")
'''

    (src_dir / "tools.py").write_text(tools_content)

    # Generate a stub for dispatcher.py in case generate_plugin_sources is called in isolation
    (src_dir / "dispatcher.py").write_text('"""Dispatcher stub"""\n')

    # Generate hooks directory and scripts
    hooks_dir = src_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (hooks_dir / "__init__.py").write_text("")
    
    # Common header for all hook scripts
    hook_header = """import sys, os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import datetime
import json
from pathlib import Path
from dispatcher import OrchestratorDispatcher

def log_action(hook_name, action, details=""):
    \"\"\"Log action to harness.log.\"\"\"
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config'))
    log_file = os.path.join(config_dir, 'harness.log')
    timestamp = datetime.datetime.now().isoformat()
    pid = os.getpid()
    
    # Ensure config dir exists
    os.makedirs(config_dir, exist_ok=True)
    
    try:
        with open(log_file, 'a') as f:
            f.write(f"[{timestamp}] [PID:{pid}] [{hook_name}] {action} - {details}\\n")
    except Exception:
        pass

def get_config_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config'))

def get_plugin_dir():
    return Path(get_config_dir()).parent

def get_project_root():
    return get_plugin_dir().parent.parent

def load_dispatcher():
    return OrchestratorDispatcher(get_config_dir())

def read_hook_payload():
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    
    # Fallback to argv for testing
    if len(sys.argv) > 1:
        return {"tool_name": sys.argv[1], "tool_args": sys.argv[2] if len(sys.argv) > 2 else ""}
    return {}

def extract_tool(payload):
    tool_name = (
        payload.get("tool_name")
        or payload.get("tool")
        or payload.get("name")
        or ""
    )
    if isinstance(tool_name, dict):
        tool_name = tool_name.get("name", "")
    tool_args = (
        payload.get("tool_args")
        or payload.get("tool_input")
        or payload.get("input")
        or payload.get("arguments")
        or {}
    )
    return str(tool_name), tool_args

def stringify(value):
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return str(value)

def setup_ready(state):
    return bool(state.get("setup_complete") and state.get("strict_enforcement_enabled"))
"""

    # Generate prompt_interceptor.py (UPS)
    prompt_interceptor_content = hook_header + '''
import xml.sax.saxutils

ROUTE_DIRECTIVES = {
    "A": "CRITICAL DIRECTIVE: Bypass Planning. Dispatch @implementer immediately with diagnose skill.",
    "B": "CRITICAL DIRECTIVE: Dispatch @planner to write a spec using harness-brainstorming.",
    "C": "CRITICAL DIRECTIVE: Answer directly using CodeGraph context. Do not mutate files.",
    "D": "CRITICAL DIRECTIVE: Dispatch @implementer directly without planning.",
}

def intercept(user_input):
    """Intercept, classify, and sanitize user input."""
    log_action("prompt_interceptor", "intercept", f"Received input of length {len(user_input) if user_input else 0}")

    if not user_input:
        return user_input

    dispatcher = load_dispatcher()
    branch = dispatcher.classify_intent(str(user_input))
    directive = ROUTE_DIRECTIVES.get(branch, ROUTE_DIRECTIVES["B"])
    sanitized = xml.sax.saxutils.escape(str(user_input))
    
    state = dispatcher._load_state()
    state["matrix_branch"] = branch
    dispatcher._save_state(state)

    routed_input = (
        f"<matrix_route branch=\\"{branch}\\">{directive}</matrix_route>\\n"
        f"<user_prompt>{sanitized}</user_prompt>"
    )
    log_action("prompt_interceptor", "intercept_complete", f"Input routed to Branch {branch}")
    return routed_input

if __name__ == "__main__":
    payload = read_hook_payload()
    print(intercept(payload.get("prompt") or payload.get("user_input") or ""))
'''
    (hooks_dir / "prompt_interceptor.py").write_text(prompt_interceptor_content)

    # Generate pre_tool_guard.py (Firewall/TDD)
    pre_tool_guard_content = hook_header + '''
import re

def is_grep_command(command):
    return bool(re.search(r"(^|\\s)(grep|rg)(\\s|$)", command))

def is_large_read(tool_args):
    if not isinstance(tool_args, dict):
        return False
    limit = tool_args.get("limit") or tool_args.get("size") or 0
    try:
        return int(limit) > 20000
    except (TypeError, ValueError):
        return False

def reject(dispatcher, state, message):
    rejections = state.get("consecutive_rejections", 0) + 1
    state["consecutive_rejections"] = rejections
    dispatcher._save_state(state)
    if rejections >= 3:
        print("[ESCALATION]: You are stuck. Use ask_user to ask for human guidance.", file=sys.stderr)
    print(message, file=sys.stderr)
    log_action("pre_tool_guard", "reject", f"{message} ({rejections} rejections)")
    sys.exit(1)

def check_tool_use(tool_name, tool_args):
    """Check if tool use is permitted."""
    log_action("pre_tool_guard", "check", f"Tool: {tool_name}")
    dispatcher = load_dispatcher()
    state = dispatcher._load_state()
    tool_text = stringify(tool_args)
    active_persona = state.get("active_persona", "orchestrator")

    if not setup_ready(state):
        # Allow but log if not set up
        log_action("pre_tool_guard", "setup_not_ready", "Strict enforcement skipped")
        return True

    if tool_name in {"Bash", "run_shell_command"} and "sudo" in tool_text:
        reject(dispatcher, state, "[VIOLATION]: sudo is not allowed from the harness runtime.")
    
    if ".env" in tool_text and tool_name in {"Bash", "run_shell_command", "Edit", "Write", "MultiEdit", "replace", "write_file", "write_to_file", "replace_file_content"}:
        reject(dispatcher, state, "[VIOLATION]: Direct .env mutation is blocked.")
        
    if tool_name in {"Bash", "run_shell_command"} and re.search(r"git\\s+push\\b[^\\n]*(--force|-f|--force-with-lease)", tool_text):
        reject(dispatcher, state, "[VIOLATION]: Force-push is blocked.")
        
    if active_persona == "orchestrator" and tool_name in {"Edit", "Write", "MultiEdit", "replace", "write_file", "write_to_file", "replace_file_content"}:
        reject(dispatcher, state, "[VIOLATION]: Orchestrators cannot write code. Use the Task() tool.")
        
    if active_persona == "implementer" and tool_name in {"Edit", "Write", "MultiEdit", "replace", "write_file", "write_to_file", "replace_file_content"} and not state.get("last_failing_test"):
        reject(dispatcher, state, "[TDD VIOLATION]: You must write and run a failing test before modifying production code.")
        
    if tool_name in {"Bash", "run_shell_command"} and is_grep_command(tool_text) and not state.get("last_codegraph_use_at"):
        reject(dispatcher, state, "[EFFICIENCY VIOLATION]: Graph-First Strategy strictly enforced. Query CodeGraph MCP before using grep.")
        
    if tool_name in {"Read", "read_file"} and is_large_read(tool_args) and not state.get("last_codegraph_use_at"):
        reject(dispatcher, state, "[EFFICIENCY VIOLATION]: Use CodeGraph before massive Read calls.")

    # Reset counter on successful tool validation
    if state.get("consecutive_rejections", 0) > 0:
        state["consecutive_rejections"] = 0
        dispatcher._save_state(state)
    log_action("pre_tool_guard", "allow", f"Tool {tool_name} allowed")
    return True

if __name__ == "__main__":
    payload = read_hook_payload()
    tool_name, tool_args = extract_tool(payload)
    check_tool_use(tool_name, tool_args)
'''
    (hooks_dir / "pre_tool_guard.py").write_text(pre_tool_guard_content)

    # Generate post_tool_monitor.py
    post_tool_monitor_content = hook_header + '''
import re

TEST_COMMAND_RE = re.compile(r"\\b(pytest|unittest|npm\\s+test|pnpm\\s+test|yarn\\s+test|cargo\\s+test|go\\s+test|mvn\\s+test|gradle\\s+test)\\b")

def extract_exit_code(payload):
    for key in ("exit_code", "returncode", "status"):
        if key in payload:
            try:
                return int(payload[key])
            except (TypeError, ValueError):
                return None
    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("exit_code", "returncode", "status"):
            if key in result:
                try:
                    return int(result[key])
                except (TypeError, ValueError):
                    return None
    return None

def record_tool_result(payload):
    dispatcher = load_dispatcher()
    state = dispatcher._load_state()
    tool_name, tool_args = extract_tool(payload)
    tool_text = stringify(tool_args)
    now = datetime.datetime.now().isoformat()

    if "codegraph" in tool_name.lower():
        state["last_codegraph_use_at"] = now
        state["last_codegraph_tool"] = tool_name

    if tool_name in {"Bash", "run_shell_command"} and TEST_COMMAND_RE.search(tool_text):
        exit_code = extract_exit_code(payload)
        test_record = {"command": tool_text, "exit_code": exit_code, "timestamp": now}
        if exit_code is not None and exit_code != 0:
            state["last_failing_test"] = test_record
            state["tdd_status"] = "red"
        elif exit_code == 0:
            state["last_passing_test"] = test_record
            if state.get("last_failing_test"):
                state["tdd_status"] = "green"

    dispatcher._save_state(state)
    log_action("post_tool_monitor", "record", f"Tool {tool_name} result recorded")
    return True

if __name__ == "__main__":
    record_tool_result(read_hook_payload())
'''
    (hooks_dir / "post_tool_monitor.py").write_text(post_tool_monitor_content)

    # Generate precompact_monitor.py
    precompact_monitor_content = hook_header + '''
def build_reminder():
    dispatcher = load_dispatcher()
    state = dispatcher._load_state()
    ddd_path = Path(get_config_dir()) / "ddd-context.json"
    ddd_context = ""
    if ddd_path.exists():
        try:
            ddd_context = json.loads(ddd_path.read_text()).get("source", "")
        except json.JSONDecodeError:
            ddd_context = ""
    return (
        "[HARNESS PERSONA REMINDER]\\n"
        f"active_persona: {state.get('active_persona')}\\n"
        f"matrix_branch: {state.get('matrix_branch')}\\n"
        f"tdd_status: {state.get('tdd_status')}\\n"
        f"verification_status: {state.get('verification_status', 'pending')}\\n"
        "DDD Context:\\n"
        f"{ddd_context[:2000]}"
    )

if __name__ == "__main__":
    reminder = build_reminder()
    log_action("precompact_monitor", "reminder", "Persona reminder emitted")
    print(reminder)
'''
    (hooks_dir / "precompact_monitor.py").write_text(precompact_monitor_content)

    # Generate stop_monitor.py (Verification guardrail)
    stop_monitor_content = hook_header + '''
import subprocess

def on_stop(reason):
    \"\"\"Monitor session stop events.\"\"\"
    log_action("stop_monitor", "stop", f"Reason: {reason}")
    dispatcher = load_dispatcher()
    state = dispatcher._load_state()
    
    if not setup_ready(state):
        return True

    # Only enforce verification gate if implementation has started
    if state.get("last_failing_test") or state.get("implementation_started"):
        verification_report = get_project_root() / "artifacts" / "verification_report.md"
        if not verification_report.exists():
            print("[QA REQUIRED]: You cannot exit. Dispatch Task(\\"@verifier\\") to perform robustness checks.", file=sys.stderr)
            sys.exit(1)

        try:
            gatekeeper = get_plugin_dir() / "scripts" / "gatekeeper.py"
            if gatekeeper.exists():
                result = subprocess.run(
                    [sys.executable, str(gatekeeper), "--phase", "3"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    print(f"[GATEKEEPER ERROR]: {result.stderr or result.stdout}", file=sys.stderr)
                    sys.exit(1)
        except Exception as e:
            log_action("stop_monitor", "error", str(e))
        
    return True

if __name__ == "__main__":
    reason = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    on_stop(reason)
'''
    (hooks_dir / "stop_monitor.py").write_text(stop_monitor_content)

    # Generate hook_validator.py
    hook_validator_content = '''"""
Validator for Claude Code orchestrator hooks.
Tests each hook in isolation with mock payloads.
"""
import json
import subprocess
import sys
import os
from pathlib import Path

def run_hook(hook_name, payload=None, args=None):
    hook_path = Path(__file__).parent / "hooks" / f"{hook_name}.py"
    cmd = [sys.executable, str(hook_path)]
    if args:
        cmd.extend(args)
    
    input_data = json.dumps(payload) if payload else ""
    
    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parent)}
    )
    return result

def test_prompt_interceptor():
    print("Testing prompt_interceptor...")
    res = run_hook("prompt_interceptor", payload={"prompt": "build a new login page"})
    if "<matrix_route branch=\\"B\\">" in res.stdout:
        print("✅ prompt_interceptor OK")
    else:
        print(f"❌ prompt_interceptor FAILED: {res.stdout}")

def test_pre_tool_guard():
    print("Testing pre_tool_guard...")
    # Test rejection of sudo
    res = run_hook("pre_tool_guard", args=["Bash", "sudo rm -rf /"])
    if "[VIOLATION]: sudo" in res.stderr:
        print("✅ pre_tool_guard (sudo rejection) OK")
    else:
        print(f"❌ pre_tool_guard FAILED: {res.stderr}")

def main():
    print("=== Orchestrator Hook Validator ===")
    test_prompt_interceptor()
    test_pre_tool_guard()
    # Add more tests as needed

if __name__ == "__main__":
    main()
'''
    (src_dir / "hook_validator.py").write_text(hook_validator_content)


def generate_pyproject(plugin_dir: Path) -> str:
    """Generate pyproject.toml for the plugin."""
    pyproject_content = """[project]
name = "orchestrator-plugin"
version = "1.0.0"
description = "Auto-generated orchestrator plugin"
requires-python = ">=3.8"

dependencies = [
    "pydantic>=2.0",
    "typing_extensions>=4.0"
]

[tool.poetry]
packages = [
    { include = "src" }
]
"""

    pyproject_path = plugin_dir / "pyproject.toml"
    with open(pyproject_path, 'w') as f:
        f.write(pyproject_content)

    return str(pyproject_path)
