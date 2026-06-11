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


# ---------------------------------------------------------------------------
# Feature-toggle helpers (Phase 0 – ECC port)
# Stdlib only; reads compiled features.json (never features.yaml).
# Fail-open semantics by default (default=True): missing file / corrupt JSON /
# missing key / traversal through a non-dict all return `default`.
# Callers may pass default=False for fail-closed behaviour.
# ---------------------------------------------------------------------------

def load_features(plugin_root) -> dict:
    """Read <plugin_root>/features.json and return a dict.

    Missing or corrupt file → returns {}.
    """
    try:
        features_path = Path(plugin_root) / "features.json"
        return json.loads(features_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def features_staleness_warning(plugin_root) -> "str | None":
    """Return a one-line warning when features.yaml is newer than features.json.

    Stdlib only; fail-open — any exception returns None (never crashes the hook).
    """
    try:
        yaml_path = Path(plugin_root) / "features.yaml"
        json_path = Path(plugin_root) / "features.json"
        if not yaml_path.exists():
            return None
        if not json_path.exists():
            return (
                "⚠ features.yaml is newer than features.json"
                " — run 'harness-wf features sync'"
            )
        if yaml_path.stat().st_mtime > json_path.stat().st_mtime:
            return (
                "⚠ features.yaml is newer than features.json"
                " — run 'harness-wf features sync'"
            )
        return None
    except Exception:
        return None


def feature_enabled(dotted_path: str, plugin_root, default: bool = True) -> bool:
    """Traverse *dotted_path* in features.json and return a bool.

    Semantics (fail-open by default, controlled by *default*):
      - Missing file, corrupt JSON → *default*
      - Missing key, traversal through non-dict → *default*
      - Boolean leaf → its value
      - Dict node → value of its "enabled" key if present, else *default*

    Intentional divergence from load_features: feature_enabled reads the JSON
    inline (rather than delegating to load_features) so that the *default*
    parameter is honoured on every failure branch independently.  load_features
    always returns {} on any error, which would collapse all failure modes into
    "missing key → default", hiding corrupt-JSON vs missing-file distinctions
    from callers that care about the distinction.
    """
    features_path = Path(plugin_root) / "features.json"
    try:
        data = json.loads(features_path.read_text(encoding="utf-8"))
    except Exception:
        return default  # missing file or corrupt JSON — honour default

    if not isinstance(data, dict):
        return default

    node = data
    for part in dotted_path.split("."):
        if not isinstance(node, dict):
            return default  # can't traverse — honour default
        if part not in node:
            return default  # missing key — honour default
        node = node[part]

    if isinstance(node, bool):
        return node
    if isinstance(node, dict):
        enabled = node.get("enabled")
        if enabled is None:
            return default  # no "enabled" key — honour default
        if isinstance(enabled, bool):
            return enabled
        return default  # non-bool "enabled" value — honour default
    return default  # unexpected leaf type — honour default
