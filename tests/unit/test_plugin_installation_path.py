
import os
from pathlib import Path
import pytest
from harness.minting_engine import mint_workspace

def test_scripts_folder_is_empty(tmp_path):
    # Setup mock project
    project_path = tmp_path / "project"
    project_path.mkdir()
    
    # Path to real boilerplate in the repo
    repo_root = Path(__file__).parent.parent.parent
    boilerplate_dir = repo_root / "src" / "harness" / "templates" / "boilerplate"
    
    # Creating a dummy orchestrator.md
    (project_path / "orchestrator.md").write_text("# Orchestrator")
    
    # Creating a dummy ONBOARDING_DOMAIN.md that requests the plugin
    (project_path / "ONBOARDING_DOMAIN.md").write_text("""
# Project
- [x] orchestrator-plugin
""")
    
    # Run mint_workspace for Claude (platform_choice "2")
    target_dir = project_path / ".claude"
    mint_workspace(
        target_dir=str(target_dir),
        selected_agents=[],
        project_path=str(project_path),
        platform_choice="2",
        boilerplate_dir=str(boilerplate_dir)
    )
    
