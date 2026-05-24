import json
from pathlib import Path
import pytest
from harness.plugin_generator import generate_orchestrator_plugin
import tempfile
import shutil
import subprocess

def test_claude_plugin_contract():
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        plugin_dir = Path(generate_orchestrator_plugin(
            project_path=str(project_path),
            project_name="test_project",
            plugin_version="1.0.0",
            harness_folder=".claude"
        ))

        # Check for plugin.json in .claude-plugin
        assert (plugin_dir / ".claude-plugin" / "plugin.json").exists(), "plugin.json should exist in .claude-plugin directory"
        assert not (plugin_dir / "settings.json").exists(), "settings.json should not exist at plugin root"
        
        # Verify plugin.json is minimal
        with open(plugin_dir / ".claude-plugin" / "plugin.json") as f:
            settings = json.load(f)
            assert settings["name"] == "orchestrator-plugin"
            assert "version" in settings
            assert "description" in settings
            assert settings["author"]["name"] == "E2G Harness"
            assert "tools" not in settings
            assert "entry_point" not in settings

        assert not (plugin_dir / "src" / "hooks").exists(), "legacy src/hooks must not be generated"
        assert not (plugin_dir / "src" / "hook_validator.py").exists(), "legacy hook_validator must not be generated"
        assert not (plugin_dir / "src" / "orchestrator_plugin.py").exists(), "legacy orchestrator_plugin.py must not be generated"
        assert not (plugin_dir / "src" / "interceptor.py").exists(), "legacy interceptor.py must not be generated"
        assert not (plugin_dir / "src" / "tools.py").exists(), "legacy tools.py must not be generated"
        assert (plugin_dir / "src" / "dispatcher.py").exists(), "dispatcher.py should remain while setup smoke tests import it"
        assert (plugin_dir / "pyproject.toml").exists(), "pyproject.toml should be copied from boilerplate"
            
        # Check for hooks/hooks.json
        assert (plugin_dir / "hooks").is_dir(), "hooks directory should exist at plugin root"
        assert (plugin_dir / "hooks" / "hooks.json").exists(), "hooks/hooks.json should exist"
        
        # Check for README.md
        assert (plugin_dir / "README.md").exists(), "README.md should exist at plugin root"
        with open(plugin_dir / "README.md") as f:
            readme = f.read()
            assert "claude --plugin-dir" in readme, "README should document the manual smoke command"
            
        # .claude-plugin should exist
        assert (plugin_dir / ".claude-plugin").exists(), ".claude-plugin directory should be generated"
        
        # Check that hooks.json has the right format
        ALLOWED_CLAUDE_EVENTS = {
            "PreToolUse", "PostToolUse", "PostToolUseFailure", "PostToolBatch",
            "Notification", "UserPromptSubmit", "UserPromptExpansion", "SessionStart",
            "SessionEnd", "Stop", "StopFailure", "SubagentStart", "SubagentStop",
            "PreCompact", "PostCompact", "PermissionRequest", "PermissionDenied",
            "Setup", "TeammateIdle", "TaskCreated", "TaskCompleted", "Elicitation",
            "ElicitationResult", "ConfigChange", "WorktreeCreate", "WorktreeRemove",
            "InstructionsLoaded", "CwdChanged", "FileChanged"
        }

        with open(plugin_dir / "hooks" / "hooks.json") as f:
            hooks_json = json.load(f)
            assert "hooks" in hooks_json
            hooks = hooks_json["hooks"]
            
            # Validate that every key is a permitted Claude Code event
            for key in hooks.keys():
                assert key in ALLOWED_CLAUDE_EVENTS, f"Invalid hook event key: '{key}'. Must be a valid Claude Code event."

            # Validate the strict 3-level structure required by Claude docs
            for event_name, matcher_groups in hooks.items():
                assert isinstance(matcher_groups, list), f"Event {event_name} must map to an array of matcher groups"
                for group in matcher_groups:
                    assert "hooks" in group, f"Matcher group in {event_name} is missing the required 'hooks' array"
                    assert isinstance(group["hooks"], list), f"'hooks' field in {event_name} matcher group must be an array"
                    for hook in group["hooks"]:
                        assert "type" in hook, f"Hook definition in {event_name} is missing the required 'type' field"
                        assert hook["type"] in ["command", "http", "mcp_tool"], f"Invalid hook type '{hook['type']}' in {event_name}"
                        if hook["type"] == "command":
                            assert "command" in hook, f"Command hook in {event_name} is missing the 'command' field"
                            assert "${CLAUDE_PLUGIN_ROOT}" in hook["command"]

            assert "UserPromptSubmit" in hooks
            assert "prompt_classifier" in hooks["UserPromptSubmit"][0]["hooks"][0]["command"]
            assert "PreToolUse" in hooks
            assert "pre_tool_guard" in hooks["PreToolUse"][0]["hooks"][0]["command"]
            assert "PostToolUse" in hooks
            assert "post_tool_observer" in hooks["PostToolUse"][0]["hooks"][0]["command"]
            assert "PostToolUseFailure" in hooks
            assert "post_tool_observer" in hooks["PostToolUseFailure"][0]["hooks"][0]["command"]
            assert "PreCompact" in hooks
            assert "precompact_handoff" in hooks["PreCompact"][0]["hooks"][0]["command"]
            assert "Stop" in hooks
            assert "stop_verifier" in hooks["Stop"][0]["hooks"][0]["command"]
            assert "ConfigChange" in hooks
            assert "config_change_guard" in hooks["ConfigChange"][0]["hooks"][0]["command"]

        marketplace_path = plugin_dir.parent / ".claude-plugin" / "marketplace.json"
        assert marketplace_path.exists(), "local marketplace manifest should exist next to plugin-generated"
        with open(marketplace_path) as f:
            marketplace = json.load(f)
        assert marketplace["name"] == "local-orchestrator-marketplace"
        assert marketplace["plugins"][0]["source"] == "./plugin-generated"

        claude = shutil.which("claude")
        if claude:
            plugin_result = subprocess.run(
                [claude, "plugin", "validate", str(plugin_dir), "--strict"],
                capture_output=True,
                text=True,
            )
            assert plugin_result.returncode == 0, plugin_result.stdout + plugin_result.stderr

            marketplace_result = subprocess.run(
                [claude, "plugin", "validate", str(plugin_dir.parent), "--strict"],
                capture_output=True,
                text=True,
            )
            assert marketplace_result.returncode == 0, marketplace_result.stdout + marketplace_result.stderr


def test_claude_plugin_regeneration_removes_legacy_payloads():
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir)
        plugin_dir = Path(generate_orchestrator_plugin(
            project_path=str(project_path),
            project_name="test_project",
            plugin_version="1.0.0",
            harness_folder=".claude"
        ))

        legacy_files = [
            plugin_dir / "src" / "orchestrator_plugin.py",
            plugin_dir / "src" / "interceptor.py",
            plugin_dir / "src" / "tools.py",
            plugin_dir / "src" / "hook_validator.py",
        ]
        for path in legacy_files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("legacy")

        legacy_hooks_dir = plugin_dir / "src" / "hooks"
        legacy_hooks_dir.mkdir(parents=True)
        (legacy_hooks_dir / "pre_tool_guard.py").write_text("legacy")

        generate_orchestrator_plugin(
            project_path=str(project_path),
            project_name="test_project",
            plugin_version="1.0.0",
            harness_folder=".claude"
        )

        for path in legacy_files:
            assert not path.exists(), f"{path.name} should be removed during regeneration"
        assert not legacy_hooks_dir.exists(), "legacy src/hooks should be removed during regeneration"
        assert (plugin_dir / "src" / "dispatcher.py").exists()
