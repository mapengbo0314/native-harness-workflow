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


def test_failed_verification_script_blocks(harness_env):
    project_root, plugin_dir = harness_env
    scripts_dir = project_root / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "verify_contract.py").write_text("import sys\nprint('nope')\nsys.exit(1)\n")

    result = run_stop_verifier(plugin_dir, project_root)

    assert result.returncode == 2
    assert "verification failed" in result.stderr.lower()


def test_successful_verification_script_passes(harness_env):
    project_root, plugin_dir = harness_env
    scripts_dir = project_root / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "verify_contract.py").write_text("print('ok')\n")

    result = run_stop_verifier(plugin_dir, project_root)

    assert result.returncode == 0
