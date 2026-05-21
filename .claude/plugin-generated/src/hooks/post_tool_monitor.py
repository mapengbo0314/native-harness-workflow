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

import re

TEST_COMMAND_RE = re.compile(r"\b(pytest|unittest|npm\s+test|pnpm\s+test|yarn\s+test|cargo\s+test|go\s+test|mvn\s+test|gradle\s+test)\b")

def extract_exit_code(payload):
    for key in ("exit_code", "returncode", "status"):
        if key in payload:
            try:
                return int(payload[key])
            except (TypeError, ValueError):
                return None
    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("exit_code", "returncode", "status"):
            if key in result:
                try:
                    return int(result[key])
                except (TypeError, ValueError):
                    return None
    return None

def record_tool_result(payload):
    dispatcher = load_dispatcher()
    state = dispatcher._load_state()
    tool_name, tool_args = extract_tool(payload)
    tool_text = stringify(tool_args)
    now = datetime.datetime.now().isoformat()

    if "codegraph" in tool_name.lower():
        state["last_codegraph_use_at"] = now
        state["last_codegraph_tool"] = tool_name

    if tool_name in {"Bash", "run_shell_command"} and TEST_COMMAND_RE.search(tool_text):
        exit_code = extract_exit_code(payload)
        test_record = {"command": tool_text, "exit_code": exit_code, "timestamp": now}
        if exit_code is not None and exit_code != 0:
            state["last_failing_test"] = test_record
            state["tdd_status"] = "red"
        elif exit_code == 0:
            state["last_passing_test"] = test_record
            if state.get("last_failing_test"):
                state["tdd_status"] = "green"

    dispatcher._save_state(state)
    log_action("post_tool_monitor", "record", f"Tool {tool_name} result recorded")
    return True

if __name__ == "__main__":
    record_tool_result(read_hook_payload())
