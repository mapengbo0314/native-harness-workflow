import sys
import json
from pathlib import Path
from hook_common import resolve_state_path, read_json

PROTECTED_PATHS = [
    ".claude/settings.json",
    ".claude/settings.local.json",
    "hooks/hooks.json",
    ".env",
    "campaign_state.json"
]

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("toolName", "")
    tool_input = input_data.get("toolInput", {})
    
    if tool_name in ["Write", "Edit", "MultiEdit", "Bash", "run_shell_command", "write_file", "replace"]:
        # Command or path checking
        path = str(tool_input.get("path", "")) + str(tool_input.get("file_path", "")) + str(tool_input.get("command", ""))
        for protected in PROTECTED_PATHS:
            if protected in path:
                print(f"Error: Access to protected path '{protected}' is blocked.", file=sys.stderr)
                sys.exit(2)
                
    # Check Branch D planner/verifier escalation
    if tool_name in ["Task", "Agent", "generalist", "planner", "verifier"]:
        state_path = resolve_state_path(input_data)
        state = read_json(state_path)
        if state.get("current_branch") == "Branch D":
            prompt = str(tool_input).lower()
            if "explicit" not in prompt:
                print("Error: Planner/verifier escalation blocked in Branch D unless explicit.", file=sys.stderr)
                sys.exit(2)
                
    # If passed
    print(json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}}))
    sys.exit(0)

if __name__ == "__main__":
    main()
