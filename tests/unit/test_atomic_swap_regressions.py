import os
import json
import shutil
from pathlib import Path
from unittest.mock import patch
from harness.minting_engine import mint_workspace, perform_smart_merge
from harness.plugin_generator import generate_orchestrator_plugin

def test_placeholder_corruption(tmp_path):
    """
    Test that placeholders are replaced with the FINAL harness name,
    not the temporary staging directory name.
    """
    project_path = tmp_path / "project"
    project_path.mkdir()
    
    # Staging in .harness_tmp
    staged_dir = project_path / ".harness_tmp"
    staged_dir.mkdir()
    
    # Final target will be .gemini
    final_harness_name = ".gemini"
    
    # Create a mock boilerplate with a placeholder
    boilerplate_dir = tmp_path / "boilerplate"
    boilerplate_dir.mkdir()
    (boilerplate_dir / "GEMINI.md").write_text("Harness in .claude")
    
    # Mint into staged_dir, but telling it the final name is final_harness_name
    mint_workspace(
        target_dir=str(staged_dir),
        selected_agents=[],
        project_path=str(project_path),
        platform_choice="1",
        boilerplate_dir=str(boilerplate_dir),
        logical_harness_name=final_harness_name
    )
    
    content = (staged_dir / "GEMINI.md").read_text()
    # If corrupted, it will be ".harness_tmp"
    # If fixed, it will be ".gemini"
    assert final_harness_name in content
    assert ".harness_tmp" not in content

def test_plugin_path_corruption(tmp_path):
    """
    Test that generated plugin.json paths use the final harness name.
    """
    project_path = tmp_path / "project"
    project_path.mkdir()
    
    # Staging in .harness_tmp
    harness_folder = ".harness_tmp"
    harness_path = project_path / harness_folder
    harness_path.mkdir()
    (harness_path / "orchestrator.md").write_text("# Orchestrator")
    
    # Final harness name will be .claude
    final_harness_name = ".claude"
    
    # Mock boilerplate
    boilerplate_dir = tmp_path / "boilerplate"
    boilerplate_dir.mkdir()
    (boilerplate_dir / "orchestrator.md").write_text("# Orchestrator")
    (boilerplate_dir / "agents").mkdir()
    (boilerplate_dir / "agents" / "tester.md").write_text("# Tester Agent")
    (boilerplate_dir / "skills").mkdir()
    (boilerplate_dir / "skills" / "test-skill").mkdir()
    (boilerplate_dir / "skills" / "test-skill" / "SKILL.md").write_text("# Test Skill")
    
    # Generate plugin
    plugin_dir_str = generate_orchestrator_plugin(
        project_path=str(project_path),
        project_name="TestProject",
        boilerplate_dir=str(boilerplate_dir),
        harness_folder=harness_folder,
        logical_harness_name=final_harness_name
    )
    
    plugin_settings_path = Path(plugin_dir_str) / ".claude-plugin" / "plugin.json"
    assert plugin_settings_path.exists()
    
    hooks_json_path = Path(plugin_dir_str) / "hooks" / "hooks.json"
    assert hooks_json_path.exists()
    
    with open(hooks_json_path, "r") as f:
        manifest = json.load(f)
        
    # Hooks use Claude's plugin-root placeholder rather than staging paths.
    for matcher_groups in manifest["hooks"].values():
        for group in matcher_groups:
            for hook in group["hooks"]:
                command = hook["command"]
                assert harness_folder not in command
                assert "${CLAUDE_PLUGIN_ROOT}" in command
                assert "uv run" in command
    # Check agents.json
    agents_json_path = Path(plugin_dir_str) / "agents.json"
    assert agents_json_path.exists()
    
    with open(agents_json_path, "r") as f:
        agents_config = json.load(f)
        for agent_name, agent_data in agents_config["agents"].items():
            # The path should refer to the logical harness, not the temporary one
            assert harness_folder not in agent_data["path"]
            assert final_harness_name in agent_data["path"]

    # Check orchestrator.json
    orch_json_path = Path(plugin_dir_str) / "orchestrator.json"
    assert orch_json_path.exists()
    
    with open(orch_json_path, "r") as f:
        orch_config = json.load(f)
        assert harness_folder not in orch_config["source"]
        assert final_harness_name in orch_config["source"]

def test_loss_of_custom_files(tmp_path):
    """
    Test that perform_smart_merge preserves files that exist in the
    existing harness but NOT in the staged boilerplate.
    """
    existing_dir = tmp_path / "existing"
    staged_dir = tmp_path / "staged"
    
    existing_dir.mkdir()
    staged_dir.mkdir()
    
    # File in both (should be merged)
    (existing_dir / "common.md").write_text("# Old")
    (staged_dir / "common.md").write_text("# New")
    
    # File ONLY in existing (should be PRESERVED)
    (existing_dir / "agents").mkdir(parents=True, exist_ok=True)
    (existing_dir / "agents" / "custom-agent.md").write_text("# Custom Agent")

    
    # Run smart merge
    perform_smart_merge(existing_dir, staged_dir)
    
    # Verify common.md merged
    assert (staged_dir / "common.md").exists()
    
    # Verify custom-agent.md PRESERVED (copied to staged)
    preserved_file = staged_dir / "agents" / "custom-agent.md"
    assert preserved_file.exists(), "Custom file from existing harness was lost!"
    assert preserved_file.read_text() == "# Custom Agent"
