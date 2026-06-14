import os
import shutil
import tempfile
import subprocess
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from harness.init.cli import main
from harness.update.manifest import read_base

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

def run_harness_init(
    project_path,
    platform_choice,
    llm="gemini",
    include_plugin=False,
    mock_should_gen_plugin=None,
    enable_rtk=False,
):
    # Mock LLM response for discovery
    with patch('subprocess.run') as mock_run, \
         patch('urllib.request.urlopen') as mock_urlopen, \
         patch('harness.init.cli.parse_args') as mock_parse_args, \
         patch('sys.exit'):

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
        args.rtk = enable_rtk
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
    plugin_path = temp_project / ".claude" / "harness-wf-plugin"
    assert plugin_path.exists()
    assert (plugin_path / ".claude-plugin" / "plugin.json").exists()
    assert (plugin_path / "hooks" / "hooks.json").exists()
    assert (plugin_path / "agents").exists()
    assert (plugin_path / "skills").exists()
    manifest_path = plugin_path / ".harness-meta.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    owned = manifest["owned"]
    assert owned
    assert manifest["render_context"]["platform"] == "claude"
    assert manifest["render_context"]["harness_dir_name"] == ".claude"
    assert manifest["render_context"]["selected_agents"] == []
    assert ".claude-plugin/plugin.json" in owned
    assert "agents/implementer.md" in owned
    assert owned["agents/implementer.md"]["class"] == "customizable"
    assert (plugin_path / ".harness-meta" / "base" / "agents" / "implementer.md.gz").exists()
    assert read_base(plugin_path, "agents/implementer.md") is not None
    assert ".env.telemetry-harness" not in owned
    assert not any(path.startswith("state/") or path == "state" for path in owned)
    assert not any("__pycache__" in path for path in owned)
    assert ".harness-meta.json" not in owned
    assert not any(path.startswith(".harness-meta/") for path in owned)
    assert not (temp_project / ".mcp.json").exists()
    for config_file in (plugin_path / "config").glob("*.json"):
        assert ".harness_tmp" not in config_file.read_text()

    check_snapshot(temp_project, "claude_plugin", [
        "CLAUDE.md",
        ".claude/harness-wf-plugin/.claude-plugin/plugin.json",
        ".claude/harness-wf-plugin/hooks/hooks.json"
    ])

def test_codex_layout(temp_project):
    run_harness_init(temp_project, "5", llm="openai")

    # Codex reads AGENTS.md (project + ~/.codex/AGENTS.md); CODEX.md is fictional.
    assert (temp_project / "AGENTS.md").exists()
    assert not (temp_project / "CODEX.md").exists()
    agents_md = (temp_project / "AGENTS.md").read_text()
    assert "codegraph" in agents_md  # harness rules pointer content
    assert "domain_ops" in agents_md

    assert not (temp_project / ".mcp.json").exists()

    # configure_cli writes the project-local codex MCP registration directly
    # (no usable codex CLI for project scope).
    codex_cfg = temp_project / ".codex" / "config.toml"
    assert codex_cfg.exists(), "codex: .codex/config.toml not written by configure_cli"
    cfg_text = codex_cfg.read_text()
    assert "[mcp_servers.domain]" in cfg_text
    assert 'DOMAIN_JSON_PATH = ".codex/domain/domain.json"' in cfg_text

    # domain.json scaffolded under the codex config dir (platform-aware seed)
    assert (temp_project / ".codex" / "domain" / "domain.json").exists()

    check_snapshot(temp_project, "codex", [
        "AGENTS.md",
        ".codex/config.toml",
    ])


def test_cursor_layout(temp_project):
    run_harness_init(temp_project, "3")

    # Cursor reads AGENTS.md (cross-vendor); .cursorrules is deprecated and the
    # copilot-instructions file is a foreign convention. The rules pointer must
    # carry the standing harness guidance (graph-first, domain_ops).
    assert (temp_project / "AGENTS.md").exists()
    assert not (temp_project / ".cursorrules").exists()
    assert not (temp_project / ".github" / "copilot-instructions.md").exists()
    agents_md = (temp_project / "AGENTS.md").read_text()
    assert "codegraph" in agents_md  # harness rules pointer content
    assert "domain_ops" in agents_md

    assert not (temp_project / ".mcp.json").exists()

    # configure_cli writes/merges the project-local cursor MCP registration.
    cursor_mcp = temp_project / ".cursor" / "mcp.json"
    assert cursor_mcp.exists(), "cursor: .cursor/mcp.json not written by configure_cli"
    data = json.loads(cursor_mcp.read_text())
    domain = data["mcpServers"]["domain"]
    assert domain["env"]["DOMAIN_JSON_PATH"] == ".cursor/domain/domain.json"

    # domain.json scaffolded under the cursor config dir (platform-aware seed)
    assert (temp_project / ".cursor" / "domain" / "domain.json").exists()

    # Native subagents: the harness's specialized agents land as Cursor-native
    # subagents under .cursor/agents/*.md (markdown + YAML frontmatter). The
    # tool names must be mapped to Cursor's tools (edit_file / run_terminal_cmd /
    # grep), NOT the Claude/foreign names.
    cursor_agents = temp_project / ".cursor" / "agents"
    assert cursor_agents.exists(), "cursor: .cursor/agents/ not generated"
    agent_files = list(cursor_agents.glob("*.md"))
    assert agent_files, "cursor: no native subagent markdown files generated"
    impl = (cursor_agents / "implementer.md")
    assert impl.exists()
    impl_text = impl.read_text()
    assert impl_text.startswith("---"), "cursor agent missing YAML frontmatter"
    assert "name: implementer" in impl_text
    assert "description:" in impl_text
    # Cursor tool names, not Claude/foreign ones.
    assert "edit_file" in impl_text
    assert "run_terminal_cmd" in impl_text
    assert "replace" not in impl_text
    assert "write_file" not in impl_text
    assert "run_shell_command" not in impl_text

    check_snapshot(temp_project, "cursor", [
        "AGENTS.md",
        ".cursor/mcp.json",
    ])


def test_claude_rtk_full_mint_and_remint_are_idempotent(temp_project):
    settings_path = temp_project / ".claude" / "settings.json"
    settings_path.parent.mkdir()
    settings_path.write_text(
        json.dumps({"permissions": {"allow": ["Read"]}}),
        encoding="utf-8",
    )

    with patch("harness.init.rtk._has_compatible_rtk", return_value=True):
        run_harness_init(
            temp_project,
            "2",
            llm="anthropic",
            include_plugin=True,
            enable_rtk=True,
        )
        run_harness_init(
            temp_project,
            "2",
            llm="anthropic",
            include_plugin=True,
            enable_rtk=True,
        )

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["permissions"] == {"allow": ["Read"]}
    commands = [
        hook["command"]
        for entry in settings["hooks"]["PreToolUse"]
        for hook in entry["hooks"]
    ]
    assert commands.count("rtk hook claude") == 1
    assert "**RTK output compression:**" in (
        temp_project / "CLAUDE.md"
    ).read_text(encoding="utf-8")


def test_codex_rtk_full_mint_adds_rules_without_claude_settings(temp_project):
    run_harness_init(
        temp_project,
        "5",
        llm="openai",
        enable_rtk=True,
    )

    rules_path = next(
        path
        for path in (temp_project / "AGENTS.md", temp_project / "CODEX.md")
        if path.exists()
    )
    assert "**RTK output compression:**" in rules_path.read_text(encoding="utf-8")
    assert not (temp_project / ".claude" / "settings.json").exists()
