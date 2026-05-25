from harness.adapters.base import PlatformAdapter
from harness.adapters.claude import ClaudeAdapter
from harness.adapters.gemini import GeminiAdapter
from harness.adapters.codex import CodexAdapter
from harness.adapters.cursor import CursorAdapter
from harness.adapters.generic import GenericAdapter

def get_adapter(platform_id: str) -> PlatformAdapter:
    """
    Returns the instantiated adapter based on a logical identifier.
    The platform_id is expected to be a string like 'gemini', 'claude', etc.
    """
    platform_id = platform_id.lower()
    if platform_id == "claude":
        return ClaudeAdapter()
    elif platform_id == "gemini":
        return GeminiAdapter()
    elif platform_id == "codex":
        return CodexAdapter()
    elif platform_id == "cursor":
        return CursorAdapter()
    else:
        return GenericAdapter()
