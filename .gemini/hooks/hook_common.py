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
    return Path(__file__).parent.parent.resolve()

def resolve_state_path(input_json: dict = None) -> Path:
    session_id = os.environ.get("LANGFUSE_SESSION_ID")
    filename = f"campaign_state_{session_id}.json" if session_id else "campaign_state.json"
    
    if input_json and "workspace_root" in input_json:
        return Path(input_json["workspace_root"]) / "state" / filename
    return resolve_plugin_root() / "state" / filename

@contextmanager
def acquire_lock(path: Path):
    lock_path = str(path) + ".lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a") as lock_file:
        try:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except ImportError:
            try:
                import msvcrt
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            except ImportError:
                pass
        try:
            yield
        finally:
            try:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except ImportError:
                try:
                    import msvcrt
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                except ImportError:
                    pass

def _write_json_nolock(path: Path, data: dict):
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, text=True)
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except Exception:
        os.unlink(tmp_path)
        raise

def atomic_write_json(path: Path | str, data: dict):
    path_obj = Path(path)
    with acquire_lock(path_obj):
        _write_json_nolock(path_obj, data)

def _safe_load_json(path_obj: Path) -> dict:
    try:
        with open(path_obj, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        if path_obj.stat().st_size == 0:
            return {}
        backup_path = path_obj.with_suffix('.json.bak')
        shutil.copy2(path_obj, backup_path)
        raise RuntimeError(f"Corrupted JSON in {path_obj}. Backed up to {backup_path}") from e
    except FileNotFoundError:
        return {}

def read_json(path: Path | str, default: dict = None) -> dict:
    if default is None:
        default = {}
    path_obj = Path(path)
    
    # Fallback/Migration for session states
    if not path_obj.exists() and path_obj.name.startswith("campaign_state_") and path_obj.name.endswith(".json"):
        base_path = path_obj.parent / "campaign_state.json"
        if base_path.exists():
            with acquire_lock(base_path):
                data = _safe_load_json(base_path)
                if data:
                    # Migrate immediately by writing to namespaced path
                    with acquire_lock(path_obj):
                        _write_json_nolock(path_obj, data)
                    return data

    if not path_obj.exists():
        return default
        
    with acquire_lock(path_obj):
        data = _safe_load_json(path_obj)
        return data if data else default

def update_state(path: Path | str, modifier_fn):
    path_obj = Path(path)
    with acquire_lock(path_obj):
        if not path_obj.exists():
            data = {}
            # Fallback check
            if path_obj.name.startswith("campaign_state_") and path_obj.name.endswith(".json"):
                base_path = path_obj.parent / "campaign_state.json"
                if base_path.exists():
                    data = _safe_load_json(base_path)
        else:
            data = _safe_load_json(path_obj)
        
        modifier_fn(data)
        
        _write_json_nolock(path_obj, data)

def append_event(state: dict, event: dict):
    if "events" not in state:
        state["events"] = []
    state["events"].append(event)

def capped_text(value: str, max_chars: int) -> str:
    if not isinstance(value, str):
        return str(value)
    if len(value) <= max_chars:
        return value
    return value[:max_chars - 3] + "..."
