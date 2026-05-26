import json
import tempfile
from pathlib import Path

from harness.init.plugin_generator import generate_orchestrator_plugin


def test_plugin_uses_single_root_hook_system():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_project = Path(tmp_dir) / "test_project"
        tmp_project.mkdir()
        (tmp_project / "docs" / "domain").mkdir(parents=True)
        (tmp_project / "docs" / "domain" / "CONTEXT.md").write_text("# Context")

        plugin_path = Path(generate_orchestrator_plugin(str(tmp_project), "TestProject"))

        assert (plugin_path / "src" / "dispatcher.py").exists()
        assert not (plugin_path / "src" / "hooks").exists()
        assert not (plugin_path / "src" / "hook_validator.py").exists()

        hooks_dir = plugin_path / "hooks"
        assert (hooks_dir / "hooks.json").exists()
        for hook_file in [
            "prompt_classifier.py",
        ]:
            assert (hooks_dir / hook_file).exists()

        hooks_config = json.loads((hooks_dir / "hooks.json").read_text())
        for groups in hooks_config["hooks"].values():
            for group in groups:
                for hook in group["hooks"]:
                    assert "${CLAUDE_PLUGIN_ROOT}" in hook["command"]
