import sys
import json
from hook_common import resolve_state_path, update_state

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        has_error = input_data.get("error") is not None or input_data.get("hook_event_name") == "PostToolUseFailure"
        
        state_path = resolve_state_path(input_data)
        captured_count = [0]
        
        def modifier(s):
            if "consecutive_tool_failures" not in s:
                s["consecutive_tool_failures"] = 0
                
            if has_error:
                s["consecutive_tool_failures"] += 1
            else:
                s["consecutive_tool_failures"] = 0
                
            captured_count[0] = s["consecutive_tool_failures"]
                
        update_state(state_path, modifier)
        
        # Check circuit breaker using captured count to avoid race condition
        if captured_count[0] >= 3:
            print("Error: Circuit breaker tripped! 3 consecutive tool failures detected.", file=sys.stderr)
            sys.exit(2)
            
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in post_tool_observer: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
