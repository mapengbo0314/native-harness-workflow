import os
import json
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from harness.plugin_generator import generate_orchestrator_plugin

def test_consecutive_failures_lock_autonomous_mode():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_project = Path(tmp_dir) / "test_project"
        tmp_project.mkdir()
        
        # Create minimal project structure
        (tmp_project / "docs" / "domain").mkdir(parents=True)
        (tmp_project / "docs" / "domain" / "CONTEXT.md").write_text("# Context")
        (tmp_project / "artifacts").mkdir()
        
        # Copy necessary files for the plugin to work
        repo_root = Path(__file__).parent.parent.parent
        # Copy instrumentation.py and dispatcher.py and database.py to where they can be found
        # Actually, generate_orchestrator_plugin handles some of this.
        
        # Generate plugin
        plugin_dir = generate_orchestrator_plugin(str(tmp_project), "TestProject")
        plugin_path = Path(plugin_dir)
        
        # Setup initial state
        config_dir = plugin_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        # Use .harness_state.json as defined in dispatcher.py
        state_file = config_dir / ".harness_state.json"
        state = {
            "setup_complete": True, 
            "strict_enforcement_enabled": True,
            "consecutive_failures": 0,
            "locked": False,
            "active_persona": "verifier"
        }
        state_file.write_text(json.dumps(state))
        
        # Path to hooks
        monitor_path = plugin_path / "src" / "hooks" / "post_tool_monitor.py"
        guard_path = plugin_path / "src" / "hooks" / "pre_tool_guard.py"
        
        # Helper to run a hook
        def run_hook(hook_path, payload):
            # Ensure the hook can find its imports
            env = {**os.environ, "PYTHONPATH": str(plugin_path / "src")}
            res = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                env=env
            )
            if res.returncode != 0:
                print(f"HOOK ERROR: {res.stderr}")
            print(f"HOOK STDOUT: {res.stdout}")
            return res

        # 1. Simulate 1st failure
        qa_report = tmp_project / "artifacts" / "qa_report.md"
        qa_report.write_text("<QA_METADATA>\n{\"status\": \"FAIL\"}\n</QA_METADATA>")
        
        payload = {
            "tool_name": "write_file",
            "tool_args": {"file_path": "artifacts/qa_report.md"}
        }
        
        result = run_hook(monitor_path, payload)
        assert result.returncode == 0, f"Monitor failed: {result.stderr}"
        
        with open(state_file, "r") as f:
            new_state = json.load(f)
            print(f"STATE AFTER 1st FAIL: {new_state}")
            assert new_state["consecutive_failures"] == 1
            assert not new_state.get("locked")

        # 2. Simulate 2nd failure
        run_hook(monitor_path, payload)
        with open(state_file, "r") as f:
            new_state = json.load(f)
            assert new_state["consecutive_failures"] == 2
            assert not new_state.get("locked")

        # 3. Simulate 3rd failure
        run_hook(monitor_path, payload)
        with open(state_file, "r") as f:
            new_state = json.load(f)
            assert new_state["consecutive_failures"] == 3
            assert new_state.get("locked") is True

        # 4. Verify pre_tool_guard blocks when locked
        payload_guard = {
            "tool_name": "read_file",
            "tool_args": {"file_path": "some_file.txt"}
        }
        result = run_hook(guard_path, payload_guard)
        assert result.returncode != 0
        assert "[CRITICAL]: Autonomous mode is locked" in result.stderr

        # 5. Verify reset on success
        qa_report.write_text("<QA_METADATA>\n{\"status\": \"PASS\"}\n</QA_METADATA>")
        # Manually unlock to test reset
        new_state["locked"] = False
        state_file.write_text(json.dumps(new_state))
        
        run_hook(monitor_path, payload)
        with open(state_file, "r") as f:
            final_state = json.load(f)
            assert final_state["consecutive_failures"] == 0

if __name__ == "__main__":
    test_consecutive_failures_lock_autonomous_mode()
    print("Verification successful!")
