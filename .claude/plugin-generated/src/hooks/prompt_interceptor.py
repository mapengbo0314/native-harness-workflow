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

import xml.sax.saxutils

ROUTE_DIRECTIVES = {
    "A": "CRITICAL DIRECTIVE: Bypass Planning. Dispatch @implementer immediately with diagnose skill.",
    "B": "CRITICAL DIRECTIVE: Use harness-brainstorming. You MUST dispatch @adversary for design grilling, then @planner to write the spec and Sphinch Marks.",
    "C": "CRITICAL DIRECTIVE: Answer directly using CodeGraph context. Do not mutate files.",
    "D": "CRITICAL DIRECTIVE: Dispatch @implementer directly without planning.",
}

def intercept(user_input):
    """Intercept, classify, and sanitize user input."""
    log_action("prompt_interceptor", "intercept", f"Received input of length {len(user_input) if user_input else 0}")

    if not user_input:
        return user_input

    dispatcher = load_dispatcher()
    branch = dispatcher.classify_intent(str(user_input))
    directive = ROUTE_DIRECTIVES.get(branch, ROUTE_DIRECTIVES["B"])
    sanitized = xml.sax.saxutils.escape(str(user_input))
    
    state = dispatcher._load_state()
    state["matrix_branch"] = branch
    dispatcher._save_state(state)

    routed_input = (
        f'<matrix_route branch="{branch}">{directive}</matrix_route>\n'
        f'<user_prompt>{sanitized}</user_prompt>'
    )
    log_action("prompt_interceptor", "intercept_complete", f"Input routed to Branch {branch}")
    return routed_input

if __name__ == "__main__":
    payload = read_hook_payload()
    print(intercept(payload.get("prompt") or payload.get("user_input") or ""))
