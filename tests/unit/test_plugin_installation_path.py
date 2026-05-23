
import os
from pathlib import Path
import pytest
from harness.minting_engine import mint_workspace

def test_setup_harness_plugin_path(tmp_path):
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
    
    setup_script_path = target_dir / "scripts" / "setup_harness.sh"
    assert setup_script_path.exists()
    
    with open(setup_script_path, "r") as f:
        content = f.read()
        
    # The problematic line:
    # if claude plugin marketplace add "$PWD/.claude/plugin-generated/.claude-plugin" --scope project
    
    # The expected correct line:
    # if claude plugin marketplace add "$PWD/.claude/plugin-generated" --scope project
    
    bad_line = 'claude plugin marketplace add "$PWD/.claude/plugin-generated/.claude-plugin" --scope project'
    good_line = 'claude plugin marketplace add "$PWD/.claude/plugin-generated" --scope project'
    
    # Debug print
    if bad_line in content:
        print("BAD LINE FOUND")
    
    assert bad_line not in content, "Found double-nested .claude-plugin path in setup_harness.sh"
    assert good_line in content, "Correct marketplace add path not found in setup_harness.sh"
