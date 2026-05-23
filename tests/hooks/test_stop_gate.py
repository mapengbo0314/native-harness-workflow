import os
import shutil
import tempfile
import subprocess
import json
import sys
from pathlib import Path
import pytest

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from harness.plugin_generator import generate_orchestrator_plugin

@pytest.fixture
def harness_env():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create necessary directories
        (tmp_path / "docs" / "domain").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "domain" / "CONTEXT.md").write_text("# DDD Context")
        
        # Generate plugin
        plugin_dir = generate_orchestrator_plugin(str(tmp_path), "TestProject")
        
        yield tmp_path, Path(plugin_dir)

def update_state(plugin_dir, updates):
    state_file = plugin_dir / "config" / ".harness_state.json"
    state = {}
    if state_file.exists():
        state = json.loads(state_file.read_text())
    state.update(updates)
    state_file.write_text(json.dumps(state))

def run_stop_monitor(plugin_dir, project_root, reason="shutdown"):
    hook_path = plugin_dir / "src" / "hooks" / "stop_monitor.py"
    
    # Set up PYTHONPATH so it can find dispatcher.py in src/
    env = {
        **os.environ,
        "PYTHONPATH": str(plugin_dir / "src")
    }
    
    result = subprocess.run(
        [sys.executable, str(hook_path), reason],
        cwd=project_root,
        capture_output=True,
        text=True,
        env=env
    )
    return result

def test_scenario_1_pre_work_exit(harness_env):
    """Scenario 1: No tests run, tdd_status is inactive or missing -> Exit code 0."""
    project_root, plugin_dir = harness_env
    
    # Case: tdd_status is inactive
    update_state(plugin_dir, {
        "setup_complete": True,
        "strict_enforcement_enabled": True,
        "tdd_status": "inactive"
    })
    result = run_stop_monitor(plugin_dir, project_root)
    assert result.returncode == 0
    
    # Case: tdd_status is missing
    update_state(plugin_dir, {
        "setup_complete": True,
        "strict_enforcement_enabled": True,
        "tdd_status": None,
        "last_failing_test": None,
        "implementation_started": False
    })
    result = run_stop_monitor(plugin_dir, project_root)
    assert result.returncode == 0

def test_scenario_2_blocked_implementation_exit(harness_env):
    """Scenario 2: implementation active but no QA report -> Exit code 1, [QA REQUIRED]."""
    project_root, plugin_dir = harness_env
    
    # Case A: tdd_status is 'green'
    update_state(plugin_dir, {
        "setup_complete": True,
        "strict_enforcement_enabled": True,
        "tdd_status": "green"
    })
    (project_root / "artifacts").mkdir(parents=True, exist_ok=True)
    qa_report = project_root / "artifacts" / "qa_report.md"
    if qa_report.exists(): qa_report.unlink()
    
    result = run_stop_monitor(plugin_dir, project_root)
    assert result.returncode == 1
    assert "[QA REQUIRED]" in result.stderr

    # Case B: tdd_status is 'red'
    update_state(plugin_dir, {
        "tdd_status": "red"
    })
    result = run_stop_monitor(plugin_dir, project_root)
    assert result.returncode == 1
    assert "[QA REQUIRED]" in result.stderr

    # Case C: implementation_started is True
    update_state(plugin_dir, {
        "tdd_status": "inactive",
        "implementation_started": True
    })
    result = run_stop_monitor(plugin_dir, project_root)
    assert result.returncode == 1
    assert "[QA REQUIRED]" in result.stderr

def test_setup_not_ready_skips_gate(harness_env):
    """If setup is not complete or strict enforcement is disabled, the gate is skipped."""
    project_root, plugin_dir = harness_env
    
    # Case: setup_complete is False
    update_state(plugin_dir, {
        "setup_complete": False,
        "strict_enforcement_enabled": True,
        "tdd_status": "green"
    })
    result = run_stop_monitor(plugin_dir, project_root)
    assert result.returncode == 0
    
    # Case: strict_enforcement_enabled is False
    update_state(plugin_dir, {
        "setup_complete": True,
        "strict_enforcement_enabled": False,
        "tdd_status": "green"
    })
    result = run_stop_monitor(plugin_dir, project_root)
    assert result.returncode == 0

def test_scenario_3_successful_verified_exit(harness_env):
    """Scenario 3: Work done, and artifacts/qa_report.md EXISTS -> Exit code 0."""
    project_root, plugin_dir = harness_env
    
    # Initialize state
    update_state(plugin_dir, {
        "setup_complete": True,
        "strict_enforcement_enabled": True,
        "tdd_status": "green"
    })
    
    # Create QA report
    artifacts_dir = project_root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "qa_report.md").write_text("# QA Report\nAll tests passed.")
    (artifacts_dir / "plan.md").write_text("# Implementation Plan\n\n## Sphinch Marks\n- [x] Verified.")
    
    result = run_stop_monitor(plugin_dir, project_root)
    assert result.returncode == 0
