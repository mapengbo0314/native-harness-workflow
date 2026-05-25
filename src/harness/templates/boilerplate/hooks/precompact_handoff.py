import sys
import json
from hook_common import resolve_project_root

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        project_root = resolve_project_root(input_data)
        handoff_path = project_root / "HANDOFF.md"
        
        goal = "Unknown Goal"
        progress = "Unknown Progress"
        next_steps = "Unknown Next Steps"
        
        content = f"# HANDOFF\n\n## Goal\n{goal}\n\n## Progress\n{progress}\n\n## Next Steps\n{next_steps}\n"
        
        # Inner try block removed. IO errors will correctly bubble to the global exception handler
        with open(handoff_path, "w") as f:
            f.write(content)
            
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in precompact_handoff: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
