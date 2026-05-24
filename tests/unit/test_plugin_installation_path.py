
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

    # The expected new validation lines:
    validation_line_1 = 'echo "Orchestrator plugin generated at .claude/plugin-generated"'
    validation_line_2 = 'echo "  claude --plugin-dir ./.claude/plugin-generated"'
    marketplace_line = 'echo "  /plugin marketplace add ./.claude"'
    install_line = 'echo "  /plugin install orchestrator-plugin@local-orchestrator-marketplace --scope project"'

    assert validation_line_1 in content, "Plugin validation path not found in setup_harness.sh"
    assert validation_line_2 in content, "Manual smoke command not found in setup_harness.sh"
    assert marketplace_line in content, "Local marketplace command not found in setup_harness.sh"
    assert install_line in content, "Plugin install command not found in setup_harness.sh"
