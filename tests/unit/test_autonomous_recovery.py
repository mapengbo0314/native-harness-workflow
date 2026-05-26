import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from harness.init.plugin_generator import generate_orchestrator_plugin


def test_root_pre_tool_guard_blocks_protected_files():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_project = Path(tmp_dir) / "test_project"
        tmp_project.mkdir()
        (tmp_project / "docs" / "domain").mkdir(parents=True)
        (tmp_project / "docs" / "domain" / "CONTEXT.md").write_text("# Context")

        plugin_path = Path(generate_orchestrator_plugin(str(tmp_project), "TestProject"))
        env = {
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(plugin_path),
            "CLAUDE_PROJECT_DIR": str(tmp_project),
        }

        result = subprocess.run(
            [sys.executable, str(plugin_path / "hooks" / "pre_tool_guard.py")],
            input=json.dumps({
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": ".env"},
            }),
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 2
        assert "blocked" in result.stderr.lower()
