import tempfile
from pathlib import Path
from harness.minting_engine import mint_workspace

def test_mint_workspace_codex_manifest():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_dir = tmp_path / "target"
        project_path = tmp_path / "project"
        boilerplate_dir = tmp_path / "boilerplate"
        
        # Create dummy directories
        project_path.mkdir()
        boilerplate_dir.mkdir()
        
        selected_agents = [
            {
                "name": "InfraManager",
                "role": "Manages infrastructure",
                "system_prompt": "You are an InfraManager.",
                "zone": "infra"
            },
            {
                "name": "ReaderAgent",
                "role": "Reads things",
                "system_prompt": "You are a ReaderAgent.",
                "zone": "core"
            }
        ]
        
        # Call mint_workspace with codex platform (5)
        mint_workspace(
            target_dir=str(target_dir),
            selected_agents=selected_agents,
            project_path=str(project_path),
            platform_choice="5", # 5 is Codex
            boilerplate_dir=str(boilerplate_dir),
            model_choice="test-model-123"
        )
        
        # Check that individual markdown files were NOT created
        assert not (target_dir / "agents").exists() or not list((target_dir / "agents").glob("*.md"))
        
        # Check that AGENTS.md was created in the root
        agents_md = target_dir / "AGENTS.md"
        assert agents_md.exists()
        
        content = agents_md.read_text()
        
        # Check first agent (InfraManager)
        assert "## infra-manager" in content
        assert "description: \"Manages infrastructure\"" in content
        assert "model: \"test-model-123\"" in content
        assert "sandbox_mode: \"workspace-write\"" in content
        assert "mcp_servers: [\"codegraph\"]" in content
        assert "You are an InfraManager." in content
        
        # Check second agent (ReaderAgent)
        assert "## reader-agent" in content
        assert "sandbox_mode: \"read-only\"" in content

