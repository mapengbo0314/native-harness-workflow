import pytest
import shutil
import tempfile
from pathlib import Path
import os
from harness.minting_engine import mint_workspace

def test_repro_unbound_local():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_dir = tmp_path / "target"
        project_path = tmp_path / "project"
        boilerplate_dir = tmp_path / "boilerplate"
        
        # Create dummy directories
        project_path.mkdir()
        boilerplate_dir.mkdir()
        # Need agents subdir in boilerplate
        (boilerplate_dir / "agents").mkdir()
        
        # To reach line 258, we need to pass some initial checks.
        # It seems it needs platform_choice that triggers should_generate_orchestrator_plugin
        # platform_choice "2" is Claude
        
        try:
            mint_workspace(
                target_dir=str(target_dir),
                selected_agents=[],
                project_path=str(project_path),
                platform_choice="2", # Claude
                boilerplate_dir=str(boilerplate_dir)
            )
        except UnboundLocalError as e:
            print(f"\nCaught expected error: {e}")
            raise e
        except Exception as e:
            print(f"\nCaught unexpected error: {type(e).__name__}: {e}")
            raise e

if __name__ == "__main__":
    test_repro_unbound_local()
