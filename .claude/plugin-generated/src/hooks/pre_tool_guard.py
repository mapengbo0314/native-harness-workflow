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

def is_grep_command(command):
    return bool(re.search(r"(^|\s)(grep|rg)(\s|$)", command))

def is_large_read(tool_args):
    if not isinstance(tool_args, dict):
        return False
    limit = tool_args.get("limit") or tool_args.get("size") or 0
    try:
        return int(limit) > 20000
    except (TypeError, ValueError):
        return False

def reject(dispatcher, state, message):
    rejections = state.get("consecutive_rejections", 0) + 1
    state["consecutive_rejections"] = rejections
    dispatcher._save_state(state)
    if rejections >= 3:
        print("[ESCALATION]: You are stuck. Use ask_user to ask for human guidance.", file=sys.stderr)
    print(message, file=sys.stderr)
    log_action("pre_tool_guard", "reject", f"{message} ({rejections} rejections)")
    sys.exit(1)

def check_tool_use(tool_name, tool_args):
    """Check if tool use is permitted."""
    log_action("pre_tool_guard", "check", f"Tool: {tool_name}")
    dispatcher = load_dispatcher()
    state = dispatcher._load_state()
    tool_text = stringify(tool_args)
    active_persona = state.get("active_persona", "orchestrator")

    if not setup_ready(state):
        # Allow but log if not set up
        log_action("pre_tool_guard", "setup_not_ready", "Strict enforcement skipped")
        return True

    if tool_name in {"Bash", "run_shell_command"} and re.search(r"(^|\s)(rm\s+-rf?|mkfs|chmod\s+-R\s+777)(\s|$)", tool_text):
        reject(dispatcher, state, "[SECURITY VIOLATION]: Dangerous commands (rm -rf, mkfs, chmod -R 777) are strictly blocked.")
        
    if tool_name in {"Bash", "run_shell_command"} and "sudo" in tool_text:
        reject(dispatcher, state, "[VIOLATION]: sudo is not allowed from the harness runtime.")
    
    if ".env" in tool_text and tool_name in {"Bash", "run_shell_command", "Edit", "Write", "MultiEdit", "replace", "write_file", "write_to_file", "replace_file_content"}:
        reject(dispatcher, state, "[VIOLATION]: Direct .env mutation is blocked.")
        
    if tool_name in {"Bash", "run_shell_command"} and re.search(r"git\s+push\b[^\n]*(--force|-f|--force-with-lease)", tool_text):
        reject(dispatcher, state, "[VIOLATION]: Force-push is blocked.")
        
    if tool_name in {"Read", "read_file", "Bash", "run_shell_command"} and ".log" in tool_text and not "extract_stacktrace.py" in tool_text:
        reject(dispatcher, state, "[EFFICIENCY VIOLATION]: Do not read raw log files directly. You MUST use run_shell_command('python3 .claude/plugin-generated/scripts/extract_stacktrace.py <file>')")
        
    if active_persona == "orchestrator" and tool_name in {"Edit", "Write", "MultiEdit", "replace", "write_file", "write_to_file", "replace_file_content"}:
        if not re.search(r"(docs/|artifacts/|tests/.*\.md)", tool_text):
            reject(dispatcher, state, "[VIOLATION]: Orchestrators can only write to .md files in docs/, artifacts/, or tests/. Use the Task() tool for code changes.")
        
    if active_persona == "implementer" and tool_name in {"Edit", "Write", "MultiEdit", "replace", "write_file", "write_to_file", "replace_file_content"} and not state.get("last_failing_test"):
        reject(dispatcher, state, "[TDD VIOLATION]: You must write and run a failing test before modifying production code.")
        
    if tool_name in {"Bash", "run_shell_command"} and is_grep_command(tool_text) and not state.get("last_codegraph_use_at"):
        reject(dispatcher, state, "[EFFICIENCY VIOLATION]: Graph-First Strategy strictly enforced. Query CodeGraph MCP before using grep.")
        
    if tool_name in {"Read", "read_file"} and is_large_read(tool_args) and not state.get("last_codegraph_use_at"):
        reject(dispatcher, state, "[EFFICIENCY VIOLATION]: Use CodeGraph before massive Read calls.")

    # Reset counter on successful tool validation
    if state.get("consecutive_rejections", 0) > 0:
        state["consecutive_rejections"] = 0
        dispatcher._save_state(state)
    log_action("pre_tool_guard", "allow", f"Tool {tool_name} allowed")
    return True

if __name__ == "__main__":
    payload = read_hook_payload()
    tool_name, tool_args = extract_tool(payload)
    check_tool_use(tool_name, tool_args)
