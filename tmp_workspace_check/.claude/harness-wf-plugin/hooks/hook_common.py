import json
import os
import tempfile
import sys
import shutil
from pathlib import Path
from contextlib import contextmanager

def resolve_project_root(input_json: dict = None) -> Path:
    if os.environ.get("GEMINI_PROJECT_DIR"):
        return Path(os.environ["GEMINI_PROJECT_DIR"]).resolve()
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve()
    if input_json and "workspace_root" in input_json:
        return Path(input_json["workspace_root"]).resolve()
    return Path.cwd().resolve()

def resolve_plugin_root() -> Path:
    if os.environ.get("GEMINI_PLUGIN_ROOT"):
        return Path(os.environ["GEMINI_PLUGIN_ROOT"]).resolve()
    if os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return Path(os.environ["CLAUDE_PLUGIN_ROOT"]).resolve()
    if os.environ.get("CURSOR_PLUGIN_ROOT"):
        return Path(os.environ["CURSOR_PLUGIN_ROOT"]).resolve()
    if os.environ.get("CODEX_PLUGIN_ROOT"):
        return Path(os.environ["CODEX_PLUGIN_ROOT"]).resolve()
    return Path(__file__).parent.parent.resolve()

def get_session_id() -> str:
    """Returns a platform-agnostic session identifier."""
    # 1. Explicit override for testing or manual injection
    if "HARNESS_SESSION_ID" in os.environ:
        return os.environ["HARNESS_SESSION_ID"]
        
    # 2. Native Claude Code Session ID
    if "CLAUDE_SESSION_ID" in os.environ:
        return os.environ["CLAUDE_SESSION_ID"]
        
    # 3. Native Gemini CLI Session ID
    if "GEMINI_SESSION_ID" in os.environ:
        return os.environ["GEMINI_SESSION_ID"]
        
    # 4. Fallback to Parent Process ID (reliable for persistent CLI runs)
    return str(os.getppid())

def capped_text(value: str, max_chars: int) -> str:
    if not isinstance(value, str):
        return str(value)
    if len(value) <= max_chars:
        return value
    return value[:max_chars - 3] + "..."