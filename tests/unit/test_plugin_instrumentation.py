import json
import tempfile
from pathlib import Path

from harness.init.plugin_generator import generate_orchestrator_plugin


def test_plugin_manifest_generation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_project = Path(tmp_dir) / "test_project"
        tmp_project.mkdir()
        (tmp_project / "docs" / "domain").mkdir(parents=True)
        (tmp_project / "docs" / "domain" / "CONTEXT.md").write_text("# Context")

        plugin_path = Path(generate_orchestrator_plugin(str(tmp_project), "TestProject"))

        # Check manifest exists
        plugin_settings_path = plugin_path / ".claude-plugin" / "plugin.json"
        assert plugin_settings_path.exists()
        
        # Check generated marketplace
        marketplace_path = tmp_project / ".claude" / ".claude-plugin" / "marketplace.json"
        assert marketplace_path.exists()
        
        # Check ddd-context.json is generated
        assert (plugin_path / "ddd-context.json").exists()

