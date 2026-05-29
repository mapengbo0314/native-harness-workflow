
import os
import json
import shutil
from pathlib import Path
from unittest.mock import patch
from harness.init.minting_engine import mint_workspace

def test_mint_workspace_does_not_generate_setup_script(tmp_path):
    # Setup mock project
    project_path = tmp_path / "project_abs_path_test"
    project_path.mkdir()

    # Path to real boilerplate in the repo
    repo_root = Path(__file__).parent.parent.parent
    boilerplate_dir = repo_root / "src" / "harness" / "templates" / "boilerplate"

    target_dir = project_path / ".gemini"

    # We call mint_workspace
    mint_workspace(
        target_dir=str(target_dir),
        selected_agents=[],
        project_path=str(project_path),
        platform_choice="1", # Gemini
        boilerplate_dir=str(boilerplate_dir)
    )    
