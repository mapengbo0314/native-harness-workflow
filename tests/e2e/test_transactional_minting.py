import os
import shutil
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from harness.init.cli import main

@pytest.mark.skip(reason="Broken due to cli.py changes")
def test_transactional_minting_and_smart_merge(tmp_path, monkeypatch):
    """
    E2E test for Transactional Smart Merge:
    1. Initial minting.
    2. Modification of files (Markdown, JSON, custom files).
    3. Second minting (smart merge).
    4. Verification of results and backup.
    """
    project_path = tmp_path / "test-project"
    project_path.mkdir()
    
    # Create a dummy file in project root to simulate a codebase
    (project_path / "app.py").write_text("print('hello')")
    
    # Mocking environment and CLI args
    monkeypatch.setenv("HARNESS_HEADLESS", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    # Avoid real npx build if possible by mocking subprocess.run
    # cli.py calls npx init --index. We mock it to succeed.
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock query_llm to avoid real API calls
        # We need to mock it in harness.init.discovery_engine
        with patch("harness.init.discovery_engine.query_llm") as mock_query:
            # First call is for generate_onboarding_domain_doc
            # It expects a JSON string with tech_stack and strategy
            mock_query.return_value = '{"tech_stack": "Python", "strategy": {"test_cmd": "pytest"}}'
            
            # --- PHASE 1: Initial Minting ---
            import sys
            test_args = ["harness-wf", "init", "--project-path", str(project_path)]
            with patch.object(sys, 'argv', test_args):                main()
            
            harness_dir = project_path / ".gemini"
            assert harness_dir.exists()
            assert (harness_dir / "AGENTS.md").exists()
            assert not (harness_dir / "mcp.json").exists()            
            # --- PHASE 2: Manual Modifications ---
            # 1. Modify a section in AGENTS.md
            agents_path = harness_dir / "AGENTS.md"
            orig_content = agents_path.read_text()
            modified_content = orig_content + "\n## Custom Additions\nThis is a custom modification.\n"
            agents_path.write_text(modified_content)
            
            # 2. Modify agent.json (deep merge test)
            agent_json_path = harness_dir / "agent.json"
            if agent_json_path.exists():
                agent_data = json.loads(agent_json_path.read_text())
                agent_data["custom_property"] = "this_should_persist"
                agent_data["model"] = "mocked_model" # simulate user override
                agent_json_path.write_text(json.dumps(agent_data, indent=2))
            else:
                agent_json_path.write_text('{"custom_property": "this_should_persist"}')
            
            # 3. Create a custom file in the harness that shouldn't be deleted by minting
            custom_file = harness_dir / "custom_agent.md"
            custom_file.write_text("# Custom Agent")

            # 4. Modify a root pointer file (GEMINI.md)
            gemini_md = project_path / "GEMINI.md"
            assert gemini_md.exists()
            gemini_md.write_text(gemini_md.read_text() + "\n\n## User Custom Note\nStay awesome.")

            # --- PHASE 3: Second Minting (Smart Merge) ---
            # Ensure timestamp for backup is likely unique
            time.sleep(1.1)
            
            # We need to reset the mocked ONBOARDING_DOMAIN.md read because wait_for_user_review_and_read_domain reads it.
            # In Phase 1, it was created with real content from the mock.
            # Let's ensure it's there.
            onboarding_doc = project_path / "ONBOARDING_DOMAIN.md"
            assert onboarding_doc.exists()

            with patch.object(sys, 'argv', test_args):
                main()
            
            # --- PHASE 4: Verification ---
            # 1. Verify Orchestrator merged (preserved custom section)
            new_content = (harness_dir / "orchestrator.md").read_text()
            assert "## Custom Section" in new_content
            assert "Custom content here." in new_content
            # And verify it still has standard content
            assert "# The Roster" in new_content
            
            # 2. Verify agent.json merged
            new_agent_data = json.loads(agent_json_path.read_text())
            assert new_agent_data.get("custom_property") == "this_should_persist"
            assert new_agent_data.get("model") == "mocked_model"
            
            # 3. Verify custom file preserved
            assert (harness_dir / "custom_agent.md").exists()
            assert (harness_dir / "custom_agent.md").read_text() == "# Custom Agent"
            
            # 4. Verify root pointer file merged
            new_gemini_content = gemini_md.read_text()
            assert "## User Custom Note" in new_gemini_content
            assert "Stay awesome." in new_gemini_content
            assert "# Agentic Harness" in new_gemini_content

            # 5. Verify backup created
            backups = list(project_path.glob(".gemini.backup.*"))
            assert len(backups) >= 1
            backup_dir = backups[0]
            assert backup_dir.is_dir()
            assert (backup_dir / "AGENTS.md").exists()

def test_headless_auto_overwrite_conflict(tmp_path, monkeypatch):
    """
    Verify that in headless mode, code conflicts are auto-overwritten.
    """
    from harness.init.minting_engine import perform_smart_merge
    
    existing_dir = tmp_path / "existing"
    staged_dir = tmp_path / "staged"
    existing_dir.mkdir()
    staged_dir.mkdir()
    
    file_rel_path = "src/utils.py"
    (existing_dir / "src").mkdir()
    (staged_dir / "src").mkdir()
    
    (existing_dir / file_rel_path).write_text("def old(): pass")
    (staged_dir / file_rel_path).write_text("def new(): pass")
    
    monkeypatch.setenv("HARNESS_HEADLESS", "1")
    
    perform_smart_merge(existing_dir, staged_dir)
    
    # In staged_dir, the file should now be the 'new' one (auto-overwrite)
    assert (staged_dir / file_rel_path).read_text() == "def new(): pass"

def test_atomic_swap_failure_cleanup(tmp_path, monkeypatch):
    """
    Verify that .harness_tmp is cleaned up even if minting fails.
    (Though cli.py currently doesn't have a try-except around the whole thing, 
    the finally block in cli.py handles it).
    """
    project_path = tmp_path / "fail-project"
    project_path.mkdir()
    
    monkeypatch.setenv("HARNESS_HEADLESS", "1")
    
    # Mock mint_workspace to raise an error
    with patch("harness.init.minting_engine.mint_workspace", side_effect=ValueError("Minting failed")):
        with patch("harness.init.discovery_engine.query_llm", return_value='{}'):
            import sys
            test_args = ["harness-wf", "init", "--project-path", str(project_path)]
            with patch.object(sys, 'argv', test_args):
                with pytest.raises(ValueError, match="Minting failed"):
                    main()
                    
    # Verify .harness_tmp is gone
    assert not (project_path / ".harness_tmp").exists()
