import os
import tempfile
from pathlib import Path
from harness.minting_engine import mint_workspace

def test_strict_generation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_path = Path(tmp_dir)
        boilerplate_dir = project_path / "boilerplate"
        boilerplate_dir.mkdir()
        (boilerplate_dir / "orchestrator.md").write_text("# Orchestrator")
        (boilerplate_dir / "AGENTS.md").write_text("# AGENTS")
        (boilerplate_dir / "rules").mkdir()
        (boilerplate_dir / "rules" / "dispatch_rules.md").write_text("# Rules")
        
        # Onboard Gemini from a clean slate
        gemini_target = project_path / ".gemini"
        mint_workspace(
            str(gemini_target), [], str(project_path), "gemini", boilerplate_dir=str(boilerplate_dir)
        )
        
        # Verify 1-to-1 generation
        assert (project_path / "GEMINI.md").exists(), "GEMINI.md should be generated"
        assert (project_path / ".gemini").exists(), ".gemini folder should be generated"
        
        # Verify no cross-contamination
        assert not (project_path / "CLAUDE.md").exists(), "CLAUDE.md should NOT be generated"
        assert not (project_path / ".cursorrules").exists(), ".cursorrules should NOT be generated"
        assert not (project_path / ".claude").exists(), ".claude folder should NOT be generated"
        print("Clean generation verified!")

if __name__ == "__main__":
    test_strict_generation()
