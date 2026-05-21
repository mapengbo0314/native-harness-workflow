import sys, os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import datetime
import json
from pathlib import Path
from dispatcher import OrchestratorDispatcher

def log_action(hook_name, action, details=""):
    """Log action to harness.log."""
    config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config'))
    log_file = os.path.join(config_dir, 'harness.log')
    timestamp = datetime.datetime.now().isoformat()
    pid = os.getpid()
    
    # Ensure config dir exists
    os.makedirs(config_dir, exist_ok=True)
    
    try:
        with open(log_file, 'a') as f:
            f.write(f"[{timestamp}] [PID:{pid}] [{hook_name}] {action} - {details}\n")
    except Exception:
        pass

def get_config_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config'))

def get_plugin_dir():
    return Path(get_config_dir()).parent

def get_project_root():
    return get_plugin_dir().parent.parent

def load_dispatcher():
    return OrchestratorDispatcher(get_config_dir())

def read_hook_payload():
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    
    # Fallback to argv for testing
    if len(sys.argv) > 1:
        return {"tool_name": sys.argv[1], "tool_args": sys.argv[2] if len(sys.argv) > 2 else ""}
    return {}

def extract_tool(payload):
    tool_name = (
        payload.get("tool_name")
        or payload.get("tool")
        or payload.get("name")
        or ""
    )
    if isinstance(tool_name, dict):
        tool_name = tool_name.get("name", "")
    tool_args = (
        payload.get("tool_args")
        or payload.get("tool_input")
        or payload.get("input")
        or payload.get("arguments")
        or {}
    )
    return str(tool_name), tool_args

def stringify(value):
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return str(value)

def setup_ready(state):
    return bool(state.get("setup_complete") and state.get("strict_enforcement_enabled"))

def build_reminder():
    dispatcher = load_dispatcher()
    state = dispatcher._load_state()
    ddd_path = Path(get_config_dir()) / "ddd-context.json"
    ddd_context = ""
    if ddd_path.exists():
        try:
            ddd_context = json.loads(ddd_path.read_text()).get("source", "")
        except json.JSONDecodeError:
            ddd_context = ""
    return (
        "[HARNESS PERSONA REMINDER]\n"
        f"active_persona: {state.get('active_persona')}\n"
        f"matrix_branch: {state.get('matrix_branch')}\n"
        f"tdd_status: {state.get('tdd_status')}\n"
        f"verification_status: {state.get('verification_status', 'pending')}\n"
        "DDD Context:\n"
        f"{ddd_context[:2000]}"
    )

if __name__ == "__main__":
    reminder = build_reminder()
    log_action("precompact_monitor", "reminder", "Persona reminder emitted")
    print(reminder)
