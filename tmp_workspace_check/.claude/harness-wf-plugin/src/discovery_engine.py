import json
import subprocess
import time
import urllib.request
import os
from llm_client import query_llm
from jinja2 import Environment, BaseLoader

class TemplateRenderer:
    def __init__(self):
        self.env = Environment(
            loader=BaseLoader(),
            block_start_string='<!--%',
            block_end_string='%-->',
            variable_start_string='<!--$',
            variable_end_string='$-->',
            comment_start_string='<!--#',
            comment_end_string='#-->',
        )

    def render_string(self, source: str, context: dict) -> str:
        template = self.env.from_string(source)
        return template.render(**context)

def acquire_mcp_context(project_path: str) -> str:
    """Acquires project context using CodeGraph and domain documentation."""
    
    context_parts = []
    
    # Priority 1: CodeGraph Symbols (Optional: If we want to seed with some high-level info)
    # For now, we rely on the agents using the MCP tool themselves, but we can check if DB exists
    codegraph_db = os.path.join(project_path, ".codegraph", "codegraph.db")
    if os.path.exists(codegraph_db):
        context_parts.append("\nCodeGraph index is available. Use `mcp_codegraph_codegraph_node` to map the architecture.")

    if context_parts:
        return "\n\n".join(context_parts)

    return None


def fetch_remote_skill(skill_url: str) -> str:
    """Fetches a skill definition from a raw GitHub URL."""
    try:
        req = urllib.request.Request(skill_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"WARNING: Failed to fetch skill from {skill_url}")
        print(f"Details: {e}")
        return None # Graceful fallback

def fetch_skill(skill_name: str, remote_url: str) -> str:
    """Fetches a skill definition from remote URL or fallback to local storage."""
    content = fetch_remote_skill(remote_url)
    if content:
        return content
        
    print(f"Attempting to load skill {skill_name} from local fallback...")
    home = os.path.expanduser("~")
    local_paths = [
        os.path.join(home, ".agents", "skills", skill_name, "SKILL.md"),
        os.path.join(home, ".gemini", "extensions", "superpowers", "skills", skill_name, "SKILL.md"),
        os.path.join(".agents", "skills", skill_name, "SKILL.md")
    ]
    
    for p in local_paths:
        if os.path.exists(p):
            try:
                with open(p, 'r') as f:
                    return f.read()
            except Exception:
                continue

    return None

