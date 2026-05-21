"""
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
