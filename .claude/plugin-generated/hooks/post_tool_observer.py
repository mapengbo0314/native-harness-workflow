import sys
import json
from hook_common import resolve_state_path, update_state

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
        
    has_error = input_data.get("error") is not None or input_data.get("type") == "PostToolUseFailure"
    
    try:
        state_path = resolve_state_path(input_data)
        
        def modifier(s):
            if "consecutive_tool_failures" not in s:
                s["consecutive_tool_failures"] = 0
                
            if has_error:
                s["consecutive_tool_failures"] += 1
            else:
                s["consecutive_tool_failures"] = 0
                
        update_state(state_path, modifier)
    except Exception:
        pass
        
    sys.exit(0)

if __name__ == "__main__":
    main()
