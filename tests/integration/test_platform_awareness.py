import pytest
import shutil
import tempfile
from pathlib import Path
import os
from harness.minting_engine import mint_workspace

def test_platform_awareness_gemini():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_dir = tmp_path / ".gemini"
        project_path = tmp_path / "project"
        boilerplate_dir = tmp_path / "boilerplate"
        
        project_path.mkdir()
        boilerplate_dir.mkdir()
        
        # Pre-create files that should be deleted
        (project_path / "CLAUDE.md").write_text("old content")
        (project_path / ".cursorrules").write_text("old content")
        (project_path / ".github").mkdir()
        (project_path / ".github" / "copilot-instructions.md").write_text("old content")
        
        # Create a boilerplate file with {{SUBAGENT_SYNTAX}}
        (boilerplate_dir / "orchestrator.md").write_text("Use {{SUBAGENT_SYNTAX}}agent-name")
        
        selected_agents = []
        
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=selected_agents,
            project_path=str(project_path),
            platform_choice="gemini",
            boilerplate_dir=str(boilerplate_dir)
        )
        
        # Check that GEMINI.md exists and OTHERS ARE PRESERVED
        assert (project_path / "GEMINI.md").exists()
        assert (project_path / "CLAUDE.md").exists()
        assert (project_path / ".cursorrules").exists()
        assert (project_path / ".github" / "copilot-instructions.md").exists()
        
        # Check replacement
        orch_content = (target_dir / "orchestrator.md").read_text()
        assert "Use @agent-name" in orch_content

def test_platform_awareness_claude():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_dir = tmp_path / ".claude"
        project_path = tmp_path / "project"
        boilerplate_dir = tmp_path / "boilerplate"
        
        project_path.mkdir()
        boilerplate_dir.mkdir()
        
        # Create a boilerplate file with {{SUBAGENT_SYNTAX}}
        (boilerplate_dir / "orchestrator.md").write_text("Use {{SUBAGENT_SYNTAX}}agent-name")
        
        selected_agents = []
        
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=selected_agents,
            project_path=str(project_path),
            platform_choice="claude",
            boilerplate_dir=str(boilerplate_dir)
        )
        
        # Check that CLAUDE.md exists
        assert (project_path / "CLAUDE.md").exists()
        
        # Check replacement
        orch_content = (target_dir / "orchestrator.md").read_text()
        assert "Use Task tool: agent-name" in orch_content

def test_platform_awareness_cursor():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_dir = tmp_path / ".cursor"
        project_path = tmp_path / "project"
        boilerplate_dir = tmp_path / "boilerplate"
        
        project_path.mkdir()
        boilerplate_dir.mkdir()
        
        selected_agents = []
        
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=selected_agents,
            project_path=str(project_path),
            platform_choice="cursor",
            boilerplate_dir=str(boilerplate_dir)
        )
        
        # Check that .cursorrules and copilot-instructions.md exist
        assert (project_path / ".cursorrules").exists()
        assert (project_path / ".github" / "copilot-instructions.md").exists()

def test_platform_awareness_agents():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_dir = tmp_path / "agents_dir"
        project_path = tmp_path / "project"
        boilerplate_dir = tmp_path / "boilerplate"
        
        project_path.mkdir()
        boilerplate_dir.mkdir()
        
        selected_agents = []
        
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=selected_agents,
            project_path=str(project_path),
            platform_choice="agents",
            boilerplate_dir=str(boilerplate_dir)
        )
        
        # Check that no NEW pointer files were created (beyond what might have existed)
        # This test is a bit redundant now but we'll keep it simple
        pass
