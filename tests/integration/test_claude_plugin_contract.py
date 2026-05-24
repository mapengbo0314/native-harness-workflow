import json
from pathlib import Path
import pytest
from harness.plugin_generator import generate_orchestrator_plugin
import tempfile
import shutil
import os

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
            assert "name" in settings
            assert "version" in settings
            assert "description" in settings
            assert "tools" in settings  # tools are defined in plugin.json
            
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
        with open(plugin_dir / "hooks" / "hooks.json") as f:
            hooks_json = json.load(f)
            assert "hooks" in hooks_json
            hooks = hooks_json["hooks"]
            assert "promptClassifier" in hooks
            assert "UserPromptSubmit" in hooks["promptClassifier"]["events"]
            assert "preToolGuard" in hooks
            assert "PreToolUse" in hooks["preToolGuard"]["events"]
            assert "postToolObserver" in hooks
            assert "PostToolUse" in hooks["postToolObserver"]["events"]
            assert "precompactHandoff" in hooks
            assert "PreCompact" in hooks["precompactHandoff"]["events"]
            assert "stopVerifier" in hooks
            assert "Stop" in hooks["stopVerifier"]["events"]
            assert "configChangeGuard" in hooks
            assert "ConfigChange" in hooks["configChangeGuard"]["events"]
