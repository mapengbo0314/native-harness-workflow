import sys
import json
from hook_common import resolve_state_path, read_json, update_state

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        state_path = resolve_state_path(input_data)
        state = read_json(state_path)
        
        if not state.get("maintenance_mode", False):
            print("Error: Config changes blocked. Enable maintenance_mode in state.", file=sys.stderr)
            sys.exit(2)
            
        def modifier(s):
            if "config_changes" not in s:
                s["config_changes"] = []
            s["config_changes"].append(input_data)
            
        update_state(state_path, modifier)
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in config_change_guard: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
