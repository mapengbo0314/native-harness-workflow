import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from harness.plugin_generator import generate_orchestrator_plugin


@pytest.fixture
def harness_env():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / "docs" / "domain").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "domain" / "CONTEXT.md").write_text("# DDD Context")
        (tmp_path / "README.md").write_text("# Test Project")

        plugin_dir = generate_orchestrator_plugin(str(tmp_path), "TestProject")

        yield tmp_path, Path(plugin_dir)


def run_stop_verifier(plugin_dir, project_root):
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(plugin_dir),
        "CLAUDE_PROJECT_DIR": str(project_root),
    }
    return subprocess.run(
        [sys.executable, str(plugin_dir / "hooks" / "stop_verifier.py")],
        input=json.dumps({"hook_event_name": "Stop"}),
        cwd=project_root,
        capture_output=True,
        text=True,
        env=env,
    )


def test_no_verification_script_passes(harness_env):
    project_root, plugin_dir = harness_env

    result = run_stop_verifier(plugin_dir, project_root)

    assert result.returncode == 0


def write_contract(path, checks):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "checks": checks}))


def test_failed_plugin_verification_contract_blocks(harness_env):
    project_root, plugin_dir = harness_env
    write_contract(
        plugin_dir / "contracts" / "default_verification_contract.json",
        [{"type": "file_exists", "path": "missing_file.txt"}],
    )

    result = run_stop_verifier(plugin_dir, project_root)

    assert result.returncode == 2
    assert "verification failed" in result.stderr.lower()
    assert "missing_file.txt" in result.stderr


def test_successful_plugin_verification_contract_passes(harness_env):
    project_root, plugin_dir = harness_env
    (project_root / "present.txt").write_text("ok")
    write_contract(
        plugin_dir / "contracts" / "default_verification_contract.json",
        [{"type": "file_exists", "path": "present.txt"}],
    )

    result = run_stop_verifier(plugin_dir, project_root)

    assert result.returncode == 0


def test_workspace_contract_overrides_plugin_contract(harness_env):
    project_root, plugin_dir = harness_env
    write_contract(
        plugin_dir / "contracts" / "default_verification_contract.json",
        [{"type": "file_exists", "path": "plugin_missing.txt"}],
    )
    write_contract(
        project_root / "contracts" / "default_verification_contract.json",
        [],
    )

    result = run_stop_verifier(plugin_dir, project_root)

    assert result.returncode == 0
