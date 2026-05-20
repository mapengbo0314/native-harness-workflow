"""Plugin generator for orchestrator-based Claude Code integration."""
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional


def generate_plugin_manifest(
    target_dir: str,
    project_name: str,
    plugin_version: str = "1.0.0"
) -> str:
    """Generate plugin.json manifest for the orchestrator plugin.

    Args:
        target_dir: Directory to generate plugin in (e.g., .claude/plugin-generated)
        project_name: Name of the project (for display)
        plugin_version: Version of the plugin

    Returns:
        Path to the generated plugin.json
    """
    plugin_dir = Path(target_dir)
    plugin_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": "orchestrator-plugin",
        "description": f"Auto-generated orchestrator plugin for {project_name}",
        "version": plugin_version,
        "author": "Harness Plugin Generator",
        "entry_point": "src/orchestrator_plugin.py",
        "requirements": [
            "pydantic>=2.0",
            "typing_extensions"
        ],
        "hooks": {
            "agent_dispatch": "src/interceptor.py:intercept_agent_dispatch"
        },
        "tools": [
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
    }

    manifest_path = plugin_dir / "plugin.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

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
                    "source": f.read()[:200]  # First 200 chars
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
    plugin_version: str = "1.0.0"
) -> str:
    """Generate a complete orchestrator plugin for the project.

    Args:
        project_path: Root path of the project
        project_name: Name of the project
        plugin_version: Version of the plugin

    Returns:
        Path to the generated plugin directory
    """
    project_path = Path(project_path)
    plugin_dir = project_path / ".claude" / "plugin-generated"

    # Create directory structure
    src_dir = plugin_dir / "src"
    config_dir = plugin_dir / "config"
    src_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    # Generate manifest
    generate_plugin_manifest(str(plugin_dir), project_name, plugin_version)

    # Export configs
    harness_dir = project_path / ".claude"
    if harness_dir.exists():
        if (harness_dir / "orchestrator.md").exists():
            export_orchestrator_config(harness_dir / "orchestrator.md", config_dir)
        if (harness_dir / "agents").exists():
            export_agents_config(harness_dir / "agents", config_dir)
        if (harness_dir / "rules").exists():
            export_rules_config(harness_dir / "rules", config_dir)

    # Export DDD context
    context_path = project_path / "docs" / "domain" / "CONTEXT.md"
    export_ddd_context(context_path, config_dir)

    # Generate plugin source files
    generate_plugin_sources(src_dir)
    
    # Copy dispatcher.py from harness directory
    harness_module_dir = Path(__file__).parent
    dispatcher_src = harness_module_dir / "dispatcher.py"
    if dispatcher_src.exists():
        shutil.copy(dispatcher_src, src_dir / "dispatcher.py")

    # Generate pyproject.toml
    generate_pyproject(plugin_dir)

    return str(plugin_dir)


def generate_plugin_sources(src_dir: Path) -> None:
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
            Result of the dispatch (simulation for now)
        """
        if not self.dispatcher.validate_against_rules(agent_name):
            return f"PermissionError: Agent '{agent_name}' violates project rules"
        
        # Simulate dispatching or routing back to orchestrator
        return (
            f"Successfully routed task to {agent_name}.\\n"
            f"Prompt received:\\n{prompt}\\n"
            f"(Orchestrator validation passed)"
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
    (src_dir / "tools.py").write_text(tools_content)

    # Generate a stub for dispatcher.py in case generate_plugin_sources is called in isolation
    (src_dir / "dispatcher.py").write_text('"""Dispatcher stub"""\n')


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
