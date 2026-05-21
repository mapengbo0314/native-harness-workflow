"""
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
