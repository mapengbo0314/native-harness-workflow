import sys
import json
import subprocess
import os
from pathlib import Path
from hook_common import resolve_project_root

def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
        
    project_root = resolve_project_root(input_data)
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent)).resolve()
    script_path = plugin_root / "scripts" / "verify_contract.py"
    
    if not script_path.exists():
        sys.exit(0)
        
    try:
        process = subprocess.run(
            [sys.executable, str(script_path), str(project_root)],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        if process.returncode != 0:
            out = process.stdout + "\n" + process.stderr
            lines = out.splitlines()[:100]
            summary = "\n".join(lines)[:10000]
            print(f"Verification failed:\n{summary}", file=sys.stderr)
            sys.exit(2)
            
    except Exception as e:
        print(f"Verification script execution error: {e}", file=sys.stderr)
        sys.exit(2)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
