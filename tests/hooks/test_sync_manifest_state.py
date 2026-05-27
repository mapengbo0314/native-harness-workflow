import os
import json
import shutil
import pytest
import subprocess
from pathlib import Path

def test_sync_manifest_moves_files(tmp_path):
    # Setup mock git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    
    docs_dir = tmp_path / "docs"
    for d in ["proposed", "inprogress", "completed", "reference"]:
        (docs_dir / d).mkdir(parents=True)
        
    manifest_path = docs_dir / "manifest.json"
    manifest_path.write_text(json.dumps({
        "docs": [
            {"name": "test-doc", "state": "inprogress", "progress_doc_path": "inprogress/test-doc-progress.md"}
        ]
    }))
    
    # Create the files in the WRONG location (e.g. still in proposed)
    proposed_file = docs_dir / "proposed" / "test-doc.md"
    proposed_file.write_text("# Test Doc")
    subprocess.run(["git", "add", "docs/proposed/test-doc.md"], cwd=tmp_path, check=True)
    
    progress_file = docs_dir / "inprogress" / "test-doc-progress.md"
    progress_file.write_text("# Progress")
    subprocess.run(["git", "add", "docs/inprogress/test-doc-progress.md"], cwd=tmp_path, check=True)
    
    # Run the script
    script_path = Path("src/harness/templates/boilerplate/scripts/sync_manifest_state.py").resolve()
    result = subprocess.run(["python3", str(script_path)], cwd=tmp_path, capture_output=True, text=True)
    
    # Verify file moved
    assert not proposed_file.exists()
    assert (docs_dir / "inprogress" / "test-doc.md").exists()
