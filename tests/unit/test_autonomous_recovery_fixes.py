import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from harness.plugin_generator import generate_orchestrator_plugin


def test_root_pre_tool_guard_path_normalization_regressions():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_project = Path(tmp_dir) / "test_project"
        tmp_project.mkdir()
        (tmp_project / "docs" / "domain").mkdir(parents=True)
        (tmp_project / "docs" / "domain" / "CONTEXT.md").write_text("# Context")
        (tmp_project / "artifacts").mkdir(parents=True)
        (tmp_project / "artifacts" / "diagnosis_report.md").write_text("# Report")
        (tmp_project / "artifacts" / "tdd_failing_test.log").write_text("AssertionError: mock failure")
        plugin_path = Path(generate_orchestrator_plugin(str(tmp_project), "TestProject"))
        state_dir = plugin_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "campaign_state.json").write_text(json.dumps({"current_branch": "D"}))
        env = {
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(plugin_path),
            "CLAUDE_PROJECT_DIR": str(tmp_project),
        }

        cases = [
            ("venv/config.py", 0),
            ("my_env_file.py", 0),
            ("./.claude/../.claude/settings.json", 2),
            ("hooks//hooks.json", 2),
            (str(tmp_project / ".env"), 2),
        ]

        for file_path, expected_returncode in cases:
            result = subprocess.run(
                [sys.executable, str(plugin_path / "hooks" / "pre_tool_guard.py")],
                input=json.dumps({
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "tool_input": {"file_path": file_path},
                }),
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == expected_returncode, file_path
