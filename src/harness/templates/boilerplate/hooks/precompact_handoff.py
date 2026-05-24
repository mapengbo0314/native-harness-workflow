import sys
import json
from hook_common import resolve_project_root, resolve_state_path, read_json, update_state

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        state_path = resolve_state_path(input_data)
        state = read_json(state_path)
        
        project_root = resolve_project_root(input_data)
        handoff_path = project_root / "HANDOFF.md"
        
        goal = state.get("goal", "Unknown Goal")
        progress = state.get("progress", "Unknown Progress")
        next_steps = state.get("next_steps", "Unknown Next Steps")
        
        content = f"# HANDOFF\n\n## Goal\n{goal}\n\n## Progress\n{progress}\n\n## Next Steps\n{next_steps}\n"
        
        # Inner try block removed. IO errors will correctly bubble to the global exception handler
        with open(handoff_path, "w") as f:
            f.write(content)
            
        def modifier(s):
            s["handoff_written"] = True
            
        update_state(state_path, modifier)
        
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in precompact_handoff: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
