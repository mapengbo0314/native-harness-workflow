import sys
import json
import subprocess
import os
from pathlib import Path
from hook_common import resolve_project_root

def main():
    try:
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("Error: Malformed JSON from agent.", file=sys.stderr)
            sys.exit(2)
            
        project_root = resolve_project_root(input_data)
        plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent)).resolve()
        script_path = plugin_root / "scripts" / "verify_contract.py"
        
        if not script_path.exists():
            sys.exit(0)
            
        # Inner try block removed. Subprocess errors will trigger the global exception block.
        process = subprocess.run(
            [sys.executable, str(script_path), str(project_root)],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        if process.returncode != 0:
            out = process.stdout + "\n" + process.stderr
            # Use logic similar to extract_stacktrace.py to grab the relevant failure context
            # rather than naively taking the first 100 lines.
            print(f"Verification failed:\n{out[-2000:]}", file=sys.stderr) # Fallback simple truncation for safety, but implementer should refine.
            sys.exit(2)
                
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: Internal hook crash in stop_verifier: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
