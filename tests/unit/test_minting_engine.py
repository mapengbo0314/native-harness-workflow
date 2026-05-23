
import os
import json
import shutil
from pathlib import Path
from unittest.mock import patch
from harness.minting_engine import mint_workspace

def test_mint_workspace_persists_strategy(tmp_path):
    # Setup mock project
    project_path = tmp_path / "project"
    project_path.mkdir()
    
    # Create a dummy requirements.txt to trigger Python detection
    (project_path / "requirements.txt").write_text("pytest")
    
    # Path to real boilerplate in the repo
    repo_root = Path(__file__).parent.parent.parent
    boilerplate_dir = repo_root / "src" / "harness" / "templates" / "boilerplate"
    
    # Mock detect_tech_stack to return a known strategy
    mock_tech_stack = {
        "stacks": ["Python"],
        "strategy": {
            "unit": "pytest tests/unit",
            "e2e": "pytest tests/e2e"
        },
        "capabilities": []
    }
    
    with patch("harness.minting_engine.detect_tech_stack", return_value=mock_tech_stack) as mock_detect:
        target_dir = project_path / ".gemini"
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=[],
            project_path=str(project_path),
            platform_choice="1",
            boilerplate_dir=str(boilerplate_dir)
        )
        
        strategy_path = target_dir / "strategy.json"
        assert strategy_path.exists(), f"strategy.json should exist at {strategy_path}"
        
        with open(strategy_path, "r") as f:
            strategy_data = json.load(f)
            
        assert strategy_data == mock_tech_stack["strategy"]
        mock_detect.assert_called_once()

def test_mint_workspace_uses_provided_tech_stack(tmp_path):
    # Setup mock project
    project_path = tmp_path / "project_provided"
    project_path.mkdir()
    
    # Path to real boilerplate in the repo
    repo_root = Path(__file__).parent.parent.parent
    boilerplate_dir = repo_root / "src" / "harness" / "templates" / "boilerplate"
    
    # Provided tech stack
    provided_tech_stack = {
        "stacks": ["Node.js"],
        "strategy": {
            "unit": "npm test",
            "e2e": "npm run e2e"
        },
        "capabilities": ["web"]
    }
    
    with patch("harness.minting_engine.detect_tech_stack") as mock_detect:
        target_dir = project_path / ".gemini"
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=[],
            project_path=str(project_path),
            platform_choice="1",
            boilerplate_dir=str(boilerplate_dir),
            tech_stack_data=provided_tech_stack
        )
        
        strategy_path = target_dir / "strategy.json"
        assert strategy_path.exists()
        
        with open(strategy_path, "r") as f:
            strategy_data = json.load(f)
            
        assert strategy_data == provided_tech_stack["strategy"]
        mock_detect.assert_not_called()

def test_mint_workspace_no_absolute_paths_in_scripts(tmp_path):
    # Setup mock project
    project_path = tmp_path / "project_abs_path_test"
    project_path.mkdir()
    
    # Path to real boilerplate in the repo
    repo_root = Path(__file__).parent.parent.parent
    boilerplate_dir = repo_root / "src" / "harness" / "templates" / "boilerplate"
    
    # Provided tech stack
    provided_tech_stack = {
        "stacks": ["Python"],
        "strategy": {
            "unit": "pytest",
            "e2e": "pytest"
        },
        "capabilities": []
    }
    
    target_dir = project_path / ".gemini"
    
    # We call mint_workspace
    mint_workspace(
        target_dir=str(target_dir),
        selected_agents=[],
        project_path=str(project_path),
        platform_choice="1", # Gemini
        boilerplate_dir=str(boilerplate_dir),
        tech_stack_data=provided_tech_stack
    )
    
    setup_script_path = target_dir / "scripts" / "setup_harness.sh"
    assert setup_script_path.exists(), "setup_harness.sh should be generated"
    
    content = setup_script_path.read_text()
    
    # FAILING CONDITION: Should NOT contain the absolute path of the project
    abs_project_path = str(project_path.resolve())
    assert abs_project_path not in content, f"Absolute path {abs_project_path} found in setup_harness.sh"
    
    # It should use relative navigation instead
    assert 'cd "$(dirname "$0")/../.."' in content or 'cd "$(dirname "${BASH_SOURCE[0]}")/../.."' in content
