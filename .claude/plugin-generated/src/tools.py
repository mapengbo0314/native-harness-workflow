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

def invoke_specific_skill_agentic_eval() -> str:
    """
    Tool function to load the 'agentic-eval' skill directly.
    """
    return invoke_skill("agentic-eval")

def invoke_specific_skill_ddd_alignment() -> str:
    """
    Tool function to load the 'ddd-alignment' skill directly.
    """
    return invoke_skill("ddd-alignment")

def invoke_specific_skill_diagnose() -> str:
    """
    Tool function to load the 'diagnose' skill directly.
    """
    return invoke_skill("diagnose")

def invoke_specific_skill_fastapi() -> str:
    """
    Tool function to load the 'fastapi' skill directly.
    """
    return invoke_skill("fastapi")

def invoke_specific_skill_grill_me() -> str:
    """
    Tool function to load the 'grill-me' skill directly.
    """
    return invoke_skill("grill-me")

def invoke_specific_skill_grill_with_docs() -> str:
    """
    Tool function to load the 'grill-with-docs' skill directly.
    """
    return invoke_skill("grill-with-docs")

def invoke_specific_skill_harness_brainstorming() -> str:
    """
    Tool function to load the 'harness-brainstorming' skill directly.
    """
    return invoke_skill("harness-brainstorming")

def invoke_specific_skill_harness_dispatching_parallel_agents() -> str:
    """
    Tool function to load the 'harness-dispatching-parallel-agents' skill directly.
    """
    return invoke_skill("harness-dispatching-parallel-agents")

def invoke_specific_skill_harness_executing_plans() -> str:
    """
    Tool function to load the 'harness-executing-plans' skill directly.
    """
    return invoke_skill("harness-executing-plans")

def invoke_specific_skill_harness_finishing_a_development_branch() -> str:
    """
    Tool function to load the 'harness-finishing-a-development-branch' skill directly.
    """
    return invoke_skill("harness-finishing-a-development-branch")
