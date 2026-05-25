# tests/unit/test_harness_resume.py
import json
import subprocess
import sys
from pathlib import Path

def test_harness_resume(tmp_path):
    plugin_dir = tmp_path / ".claude" / "plugin-generated"
    plugin_dir.mkdir(parents=True)
    state_dir = plugin_dir / "state"
    state_dir.mkdir()
    state_path = state_dir / "campaign_state.json"
    
    with open(state_path, "w") as f:
        json.dump({
            "tasks": {
                "current_goal": "Deploy app",
                "steps": [
                    {"name": "Build", "status": "completed"},
                    {"name": "Test", "status": "pending"}
                ]
            }
        }, f)

    script_path = Path("src/harness/templates/boilerplate/scripts/harness_resume.py")
    env = {"CLAUDE_PLUGIN_ROOT": str(plugin_dir)}
    res = subprocess.run(
        [sys.executable, str(script_path)],
        env=env, capture_output=True, text=True
    )
    
    assert res.returncode == 0
    out = res.stdout
    assert "Current Goal: Deploy app" in out
    assert "[x] Build" in out
    assert "[ ] Test" in out