"""
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
                return f"\n=== MANDATE: {rule_name.upper()} ===\n" + rules[rule_name] + "\n===========================\n"
            return match.group(0)
            
        resolved_source = re.sub(r'@\.\./rules/([a-zA-Z0-9_-]+\.md)', replace_rule, agent_source)
        
        return (
            f"[ORCHESTRATOR APPROVED TASK DISPATCH]\n"
            f"You have been authorized to execute this task as: @{agent_name}\n\n"
            f"=== AGENT PERSONA / INSTRUCTIONS ===\n"
            f"{resolved_source}\n\n"
            f"=== TASK TO EXECUTE ===\n"
            f"{prompt}\n\n"
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
