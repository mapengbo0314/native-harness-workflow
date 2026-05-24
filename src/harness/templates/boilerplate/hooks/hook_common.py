import json
import os
import fcntl
import tempfile
from pathlib import Path
from contextlib import contextmanager

def resolve_project_root(input_json: dict = None) -> Path:
    if input_json and "workspace_root" in input_json:
        return Path(input_json["workspace_root"])
    return Path.cwd()

def resolve_plugin_root() -> Path:
    return Path(__file__).parent.parent

def resolve_state_path(input_json: dict = None) -> Path:
    return resolve_plugin_root() / "state" / "campaign_state.json"

@contextmanager
def acquire_lock(path: Path):
    lock_path = str(path) + ".lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

def atomic_write_json(path: Path | str, data: dict):
    path_obj = Path(path)
    with acquire_lock(path_obj):
        tmp_fd, tmp_path = tempfile.mkstemp(dir=path_obj.parent, text=True)
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path_obj))
        except Exception:
            os.unlink(tmp_path)
            raise

def read_json(path: Path | str, default: dict = None) -> dict:
    if default is None:
        default = {}
    path_obj = Path(path)
    if not path_obj.exists():
        return default
        
    with acquire_lock(path_obj):
        try:
            with open(path_obj, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

def update_state(path: Path | str, modifier_fn):
    path_obj = Path(path)
    with acquire_lock(path_obj):
        if not path_obj.exists():
            data = {}
        else:
            try:
                with open(path_obj, "r") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = {}
        
        modifier_fn(data)
        
        tmp_fd, tmp_path = tempfile.mkstemp(dir=path_obj.parent, text=True)
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(path_obj))
        except Exception:
            os.unlink(tmp_path)
            raise

def append_event(state: dict, event: dict):
    if "events" not in state:
        state["events"] = []
    state["events"].append(event)
    return state

def capped_text(value: str, max_chars: int) -> str:
    if not isinstance(value, str):
        return str(value)
    if len(value) <= max_chars:
        return value
    return value[:max_chars - 3] + "..."
