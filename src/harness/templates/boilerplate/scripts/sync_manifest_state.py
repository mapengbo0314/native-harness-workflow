import os
import json
import subprocess
from pathlib import Path

def move_tracked_file(src: Path, dest: Path, project_root: Path, action: str = "Moving"):
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[DocSync] {action} {src.relative_to(project_root)} to {dest.relative_to(project_root)}")
    try:
        try:
            subprocess.run(["git", "mv", str(src), str(dest)], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # Fallback to normal mv if not tracked by git
            src.rename(dest)
    except Exception as e:
        print(f"[DocSync] Warning: Failed to move {src} to {dest}: {e}")

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
                    move_tracked_file(wrong_path, expected_path, project_root)
                    
        # Handle progress docs for 'completed' state
        progress_path = doc.get("progress_doc_path")
        if state == "completed" and progress_path and progress_path.startswith("inprogress/"):
            # Progress doc needs to move to reference
            wrong_prog_path = docs_dir / progress_path
            new_prog_rel = progress_path.replace("inprogress/", "reference/", 1)
            expected_prog_path = docs_dir / new_prog_rel
            
            if wrong_prog_path.exists():
                move_tracked_file(wrong_prog_path, expected_prog_path, project_root, action="Archiving progress doc")
                    
                # We do NOT rewrite the manifest progress_doc_path here to avoid infinite loops with git commits,
                # the prompt templates will instruct agents to update the manifest path.

if __name__ == "__main__":
    main()
