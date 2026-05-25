# tests/unit/test_task_tracker.py
import json
import subprocess
import sys
from pathlib import Path

def test_task_tracker(tmp_path):
    # Setup mock plugin environment
    plugin_dir = tmp_path / ".claude" / "plugin-generated"
    plugin_dir.mkdir(parents=True)
    
    state_dir = plugin_dir / "state"
    state_dir.mkdir()
    state_path = state_dir / "campaign_state.json"
    
    # Initialize state
    with open(state_path, "w") as f:
        json.dump({"tasks": {"current_goal": "", "steps": []}}, f)

    script_path = Path("src/harness/templates/boilerplate/scripts/task_tracker.py")
    
    # Set goal
    env = {"CLAUDE_PLUGIN_ROOT": str(plugin_dir)}
    res = subprocess.run(
        [sys.executable, str(script_path), "--set-goal", "Finish phase 6"],
        env=env, capture_output=True, text=True
    )
    assert res.returncode == 0
    
    # Add step
    res = subprocess.run(
        [sys.executable, str(script_path), "--add-step", "Write tests"],
        env=env, capture_output=True, text=True
    )
    assert res.returncode == 0
    
    # Complete step
    res = subprocess.run(
        [sys.executable, str(script_path), "--complete-step", "Write tests"],
        env=env, capture_output=True, text=True
    )
    assert res.returncode == 0
    
    with open(state_path, "r") as f:
        data = json.load(f)
    
    assert data["tasks"]["current_goal"] == "Finish phase 6"
    assert len(data["tasks"]["steps"]) == 1
    assert data["tasks"]["steps"][0]["name"] == "Write tests"
    assert data["tasks"]["steps"][0]["status"] == "completed"