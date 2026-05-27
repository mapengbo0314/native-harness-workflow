import os
import json
import subprocess
from pathlib import Path

def main():
    project_root = Path.cwd()
    docs_dir = project_root / "docs"
    manifest_path = docs_dir / "manifest.json"
    
    if not manifest_path.exists():
        return
        
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except Exception:
        return
        
    for doc in manifest.get("docs", []):
        name = doc.get("name")
        state = doc.get("state")
        if not name or not state:
            continue
            
        target_dir = docs_dir / state
        expected_path = target_dir / f"{name}.md"
        
        # If the file is not in the right place, find and move it
        if not expected_path.exists():
            # Look for it in other state directories
            for other_state in ["proposed", "inprogress", "completed", "reference"]:
                if other_state == state:
                    continue
                
                wrong_path = docs_dir / other_state / f"{name}.md"
                if wrong_path.exists():
                    print(f"[DocSync] Moving {wrong_path.relative_to(project_root)} to {expected_path.relative_to(project_root)}")
                    # Use git mv to preserve history if tracked
                    try:
                        subprocess.run(["git", "mv", str(wrong_path), str(expected_path)], check=True, capture_output=True)
                    except subprocess.CalledProcessError:
                        # Fallback to normal mv if not tracked by git
                        wrong_path.rename(expected_path)
                    
        # Handle progress docs for 'completed' state
        progress_path = doc.get("progress_doc_path")
        if state == "completed" and progress_path and progress_path.startswith("inprogress/"):
            # Progress doc needs to move to reference
            wrong_prog_path = docs_dir / progress_path
            new_prog_rel = progress_path.replace("inprogress/", "reference/", 1)
            expected_prog_path = docs_dir / new_prog_rel
            
            if wrong_prog_path.exists():
                print(f"[DocSync] Archiving progress doc {wrong_prog_path.relative_to(project_root)} to {expected_prog_path.relative_to(project_root)}")
                try:
                    subprocess.run(["git", "mv", str(wrong_prog_path), str(expected_prog_path)], check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    wrong_prog_path.rename(expected_prog_path)
                    
                # We do NOT rewrite the manifest progress_doc_path here to avoid infinite loops with git commits,
                # the prompt templates will instruct agents to update the manifest path.

if __name__ == "__main__":
    main()
