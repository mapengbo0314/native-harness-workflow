import os
import shutil
import tempfile
import subprocess
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from harness.init.cli import main

def check_snapshot(project_path: Path, platform: str, relative_paths: list[str]):
    snapshot_dir = Path("tests/fixtures/snapshots") / platform
    update_snapshots = os.environ.get("UPDATE_SNAPSHOTS") == "1"
    
    # Capture both original and resolved paths for robust sanitization
    project_root_str = str(project_path)
    resolved_root_str = str(project_path.resolve())

    if update_snapshots:
        snapshot_dir.mkdir(parents=True, exist_ok=True)

    for rel_path in relative_paths:
        file_path = project_path / rel_path
        # Use a safe filename for the snapshot
        snap_file = snapshot_dir / f"{rel_path}.txt"
        
        if not file_path.exists():
            # If a critical file is missing, it should fail anyway if we're not updating
            if not update_snapshots:
                pytest.fail(f"Critical file {rel_path} was not generated.")
            continue

        with open(file_path, "r") as f:
            current_content = f.read()

        # Sanitize: replace absolute project paths with placeholder
        # Order matters: replace longer (resolved) path first
        for p in sorted([project_root_str, resolved_root_str], key=len, reverse=True):
            current_content = current_content.replace(p, "<PROJECT_ROOT>")
            # Handle macOS /private prefix explicitly
            if p.startswith("/var/"):
                current_content = current_content.replace("/private" + p, "<PROJECT_ROOT>")
            # Handle escaped JSON paths
            escaped_p = p.replace("/", "\\/")
            current_content = current_content.replace(escaped_p, "<PROJECT_ROOT>")

        # Also replace the basename if it's still there (e.g. in descriptions)
        current_content = current_content.replace(project_path.name, "<PROJECT_BASENAME>")

        if update_snapshots:
            snap_file.parent.mkdir(parents=True, exist_ok=True)
            with open(snap_file, "w") as f:
                f.write(current_content)
        else:
            if not snap_file.exists():
                pytest.fail(f"Snapshot missing for {rel_path} at {snap_file}. Run with UPDATE_SNAPSHOTS=1 to generate.")
            
            with open(snap_file, "r") as f:
                expected_content = f.read()
            
            assert current_content == expected_content, f"Snapshot mismatch for {rel_path}. Run with UPDATE_SNAPSHOTS=1 to update if this change is intentional."

@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Copy boilerplate
        src_path = Path("tests/fixtures/boilerplates/sample-py-app")
        dest_path = Path(tmp_dir)
        shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
        
        # Init git as it might be needed by some tools
        subprocess.run(["git", "init"], cwd=tmp_dir, check=True, capture_output=True)
        
        yield dest_path

def run_harness_init(project_path, platform_choice, llm="gemini", include_plugin=False, mock_should_gen_plugin=None):
    # Mock LLM response for discovery
    with patch('harness.init.discovery_engine.query_llm') as mock_query_llm, \
         patch('subprocess.run') as mock_run, \
         patch('urllib.request.urlopen') as mock_urlopen, \
         patch('harness.init.cli.parse_args') as mock_parse_args, \
         patch('sys.exit'):
        
        # Mock LLM response
        skills = []
        if include_plugin:
            skills.append({"name": "orchestrator-plugin", "url": "https://github.com/example/plugin", "type": "extension"})
        
        mock_query_llm.return_value = json.dumps({
            "sme_name": "test-sme", 
            "core_domain_value": "test value", 
            "invariants": ["inv1"], 
            "glossary": {"term": "def"}, 
            "domain_events": ["event1"], 
            "skills": skills, 
            "mcps": []
        })
        
        # Mock subprocess.run for codegraph init
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock urlopen for skill downloads (empty response)
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b""

        args = MagicMock()
        args.command = "init"
        args.project_path = str(project_path)
        args.llm = llm
        args.model = None
        args.bundle = None
        mock_parse_args.return_value = args

        env = {
            "HARNESS_HEADLESS": "1",
            "HARNESS_PLATFORM": platform_choice,
            "GEMINI_API_KEY": "fake-key",
            "ANTHROPIC_API_KEY": "fake-key",
            "OPENAI_API_KEY": "fake-key",
            "PATH": os.environ.get("PATH", "")
        }
        
        with patch.dict(os.environ, env):
            try:
                main()
            except SystemExit:
                pass

def test_gemini_layout(temp_project):
    run_harness_init(temp_project, "1")
    
    assert (temp_project / "GEMINI.md").exists()
    assert (temp_project / ".gemini").exists()
    assert (temp_project / ".gemini" / "agents").exists()
    assert (temp_project / ".gemini" / "rules").exists()
    assert (temp_project / ".gemini" / "skills").exists()
    assert not (temp_project / ".gemini" / "scripts").exists() or not list((temp_project / ".gemini" / "scripts").glob("*.sh"))
    assert not (temp_project / ".mcp.json").exists()

    check_snapshot(temp_project, "gemini", [
        "GEMINI.md"
    ])

def test_claude_plugin_layout(temp_project):
    # Test Claude WITH plugin
    run_harness_init(temp_project, "2", llm="anthropic", include_plugin=True, mock_should_gen_plugin=True)
    
    assert (temp_project / "CLAUDE.md").exists()
    assert (temp_project / ".claude").exists()
    
    # When plugin is generated, agents/ and skills/ are moved into the plugin and cleaned up from top level
    assert not (temp_project / ".claude" / "agents").exists()
    assert not (temp_project / ".claude" / "skills").exists()
    
    # Check plugin structure
    plugin_path = temp_project / ".claude" / "plugin-generated"
    assert plugin_path.exists()
    assert (plugin_path / ".claude-plugin" / "plugin.json").exists()
    assert (plugin_path / "hooks" / "hooks.json").exists()
    assert (plugin_path / "agents").exists()
    assert (plugin_path / "skills").exists()
    assert not (temp_project / ".mcp.json").exists()
    for config_file in (plugin_path / "config").glob("*.json"):
        assert ".harness_tmp" not in config_file.read_text()

    check_snapshot(temp_project, "claude_plugin", [
        "CLAUDE.md",
        ".claude/plugin-generated/.claude-plugin/plugin.json",
        ".claude/plugin-generated/hooks/hooks.json"
    ])

def test_codex_layout(temp_project):
    run_harness_init(temp_project, "5", llm="openai")
    
    assert (temp_project / "CODEX.md").exists()
    # AGENTS.md is inside .codex
    assert (temp_project / ".codex" / "AGENTS.md").exists()
    
    assert not (temp_project / ".mcp.json").exists()
    check_snapshot(temp_project, "codex", [
        "CODEX.md",
        ".codex/AGENTS.md"
    ])
