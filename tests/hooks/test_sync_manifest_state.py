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
    
    env = os.environ.copy()
    env["HARNESS_PLUGIN_ROOT"] = str(tmp_path / "plugin-generated")
    
    # Run the script
    script_path = Path("src/harness/templates/boilerplate/scripts/sync_manifest_state.py").resolve()
    result = subprocess.run(["python3", str(script_path)], cwd=tmp_path, env=env, capture_output=True, text=True)
    
    # Verify file moved
    assert not proposed_file.exists()
    assert (docs_dir / "inprogress" / "test-doc.md").exists()

def test_sync_manifest_moves_progress_doc_on_completion(tmp_path):
    # Setup mock git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    
    docs_dir = tmp_path / "docs"
    for d in ["proposed", "inprogress", "completed", "reference"]:
        (docs_dir / d).mkdir(parents=True)
        
    manifest_path = docs_dir / "manifest.json"
    manifest_path.write_text(json.dumps({
        "docs": [
            {"name": "test-doc", "state": "completed", "progress_doc_path": "inprogress/test-doc-progress.md"}
        ]
    }))
    
    # Create the files in the WRONG location (e.g. still in inprogress)
    inprogress_file = docs_dir / "inprogress" / "test-doc.md"
    inprogress_file.write_text("# Test Doc")
    subprocess.run(["git", "add", "docs/inprogress/test-doc.md"], cwd=tmp_path, check=True)
    
    progress_file = docs_dir / "inprogress" / "test-doc-progress.md"
    progress_file.write_text("# Progress")
    subprocess.run(["git", "add", "docs/inprogress/test-doc-progress.md"], cwd=tmp_path, check=True)
    
    env = os.environ.copy()
    env["HARNESS_PLUGIN_ROOT"] = str(tmp_path / "plugin-generated")
    
    # Run the script
    script_path = Path("src/harness/templates/boilerplate/scripts/sync_manifest_state.py").resolve()
    result = subprocess.run(["python3", str(script_path)], cwd=tmp_path, env=env, capture_output=True, text=True)
    
    # Verify both files moved to the correct locations
    assert not inprogress_file.exists()
    assert (docs_dir / "completed" / "test-doc.md").exists()
    assert not progress_file.exists()
    assert (docs_dir / "reference" / "test-doc-progress.md").exists()

def test_sync_manifest_moves_progress_doc_when_main_doc_already_completed(tmp_path):
    # Setup mock git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    
    docs_dir = tmp_path / "docs"
    for d in ["proposed", "inprogress", "completed", "reference"]:
        (docs_dir / d).mkdir(parents=True)
        
    manifest_path = docs_dir / "manifest.json"
    manifest_path.write_text(json.dumps({
        "docs": [
            {"name": "test-doc", "state": "completed", "progress_doc_path": "inprogress/test-doc-progress.md"}
        ]
    }))
    
    # Create main doc in CORRECT location
    completed_file = docs_dir / "completed" / "test-doc.md"
    completed_file.write_text("# Test Doc")
    subprocess.run(["git", "add", "docs/completed/test-doc.md"], cwd=tmp_path, check=True)
    
    # Create progress doc in WRONG location
    progress_file = docs_dir / "inprogress" / "test-doc-progress.md"
    progress_file.write_text("# Progress")
    subprocess.run(["git", "add", "docs/inprogress/test-doc-progress.md"], cwd=tmp_path, check=True)
    
    env = os.environ.copy()
    env["HARNESS_PLUGIN_ROOT"] = str(tmp_path / "plugin-generated")
    
    # Run the script
    script_path = Path("src/harness/templates/boilerplate/scripts/sync_manifest_state.py").resolve()
    result = subprocess.run(["python3", str(script_path)], cwd=tmp_path, env=env, capture_output=True, text=True)
    
    # Verify main doc remains, progress doc moved
    assert completed_file.exists()
    assert not progress_file.exists()
    assert (docs_dir / "reference" / "test-doc-progress.md").exists()

