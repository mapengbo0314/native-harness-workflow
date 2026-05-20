import pytest
from pathlib import Path
import tempfile
import json
import shutil
from harness.minting_engine import mint_workspace

def test_mcp_config_filename_gemini():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_dir = tmp_path / ".gemini"
        project_path = tmp_path
        boilerplate_dir = tmp_path / "boilerplate"
        boilerplate_dir.mkdir()
        
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=[],
            project_path=str(project_path),
            platform_choice="gemini",
            boilerplate_dir=str(boilerplate_dir)
        )
        
        # We now generate mcp.json uniformly as a reference/fallback
        assert (target_dir / "mcp.json").exists()
        
        with open(target_dir / "mcp.json", "r") as f:
            config = json.load(f)
            assert "mcpServers" in config
            assert "codegraph" in config["mcpServers"]
            command_args = " ".join(config["mcpServers"]["codegraph"]["args"])
            assert "@colbymchenry/codegraph" in command_args
def test_mcp_config_filename_claude():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_dir = tmp_path / ".claude"
        project_path = tmp_path
        boilerplate_dir = tmp_path / "boilerplate"
        boilerplate_dir.mkdir()
        
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=[],
            project_path=str(project_path),
            platform_choice="claude",
            boilerplate_dir=str(boilerplate_dir)
        )
        
        assert (target_dir / "mcp.json").exists()

def test_setup_harness_contains_mcp_instructions_claude():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_dir = tmp_path / ".claude"
        project_path = tmp_path
        boilerplate_dir = tmp_path / "boilerplate"
        boilerplate_dir.mkdir()
        
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=[],
            project_path=str(project_path),
            platform_choice="claude",
            boilerplate_dir=str(boilerplate_dir)
        )
        
        setup_script = target_dir / "scripts" / "setup_harness.sh"
        assert setup_script.exists()
        content = setup_script.read_text()
        assert "claude mcp add --scope project codegraph" in content

def test_setup_harness_contains_mcp_instructions_gemini():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_dir = tmp_path / ".gemini"
        project_path = tmp_path
        boilerplate_dir = tmp_path / "boilerplate"
        boilerplate_dir.mkdir()
        
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=[],
            project_path=str(project_path),
            platform_choice="gemini",
            boilerplate_dir=str(boilerplate_dir)
        )
        
        setup_script = target_dir / "scripts" / "setup_harness.sh"
        assert setup_script.exists()
        content = setup_script.read_text()
        assert "gemini mcp add codegraph npx" in content
