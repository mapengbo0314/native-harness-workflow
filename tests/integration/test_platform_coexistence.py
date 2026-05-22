import os
import shutil
import tempfile
from pathlib import Path
from harness.minting_engine import mint_workspace

def test_platform_coexistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        boilerplate_dir = project_path / "boilerplate"
        boilerplate_dir.mkdir()
        (boilerplate_dir / "orchestrator.md").write_text("# Orchestrator")
        (boilerplate_dir / "AGENTS.md").write_text("# AGENTS")
        (boilerplate_dir / "rules").mkdir()
        (boilerplate_dir / "rules" / "dispatch_rules.md").write_text("# Rules")
        
        # 1. Onboard Gemini
        gemini_target = project_path / ".gemini"
        mint_workspace(
            str(gemini_target),
            [], # selected_agents
            str(project_path),
            "1", # gemini
            boilerplate_dir=str(boilerplate_dir)
        )
        
        assert (project_path / "GEMINI.md").exists(), "GEMINI.md should exist after onboarding Gemini"
        assert (project_path / ".gemini").exists(), ".gemini folder should exist"
        
        # 2. Onboard Claude
        claude_target = project_path / ".claude"
        mint_workspace(
            str(claude_target),
            [],
            str(project_path),
            "2", # claude
            boilerplate_dir=str(boilerplate_dir)
        )
        
        assert (project_path / "CLAUDE.md").exists(), "CLAUDE.md should exist after onboarding Claude"
        assert (project_path / ".claude").exists(), ".claude folder should exist"
        
        # Verify coexistence
        assert (project_path / "GEMINI.md").exists(), "GEMINI.md should STILL exist after onboarding Claude"
        assert (project_path / ".gemini").exists(), ".gemini folder should STILL exist"
        
        # Verify pointer content
        gemini_content = (project_path / "GEMINI.md").read_text()
        assert ".gemini/AGENTS.md" in gemini_content, f"GEMINI.md should point to .gemini/AGENTS.md, got: {gemini_content}"
        
        claude_content = (project_path / "CLAUDE.md").read_text()
        assert ".claude/AGENTS.md" in claude_content, f"CLAUDE.md should point to .claude/AGENTS.md, got: {claude_content}"

if __name__ == "__main__":
    try:
        test_platform_coexistence()
        print("Test PASSED: Platforms coexist!")
    except AssertionError as e:
        print(f"Test FAILED: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
