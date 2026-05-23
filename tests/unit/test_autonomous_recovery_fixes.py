import os
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from harness.plugin_generator import generate_orchestrator_plugin

def test_autonomous_recovery_fixes_verification():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_project = Path(tmp_dir) / "test_project"
        tmp_project.mkdir()
        
        # Create minimal project structure
        (tmp_project / "docs" / "domain").mkdir(parents=True)
        (tmp_project / "docs" / "domain" / "CONTEXT.md").write_text("# Context")
        (tmp_project / "artifacts").mkdir()
        
        # Generate plugin
        plugin_dir = generate_orchestrator_plugin(str(tmp_project), "TestProject")
        plugin_path = Path(plugin_dir)
        
        # Setup initial state
        config_dir = plugin_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        state_file = config_dir / ".harness_state.json"
        state = {
            "setup_complete": True, 
            "strict_enforcement_enabled": True,
            "consecutive_failures": 1, # Start with 1 failure
            "locked": False,
            "active_persona": "verifier"
        }
        state_file.write_text(json.dumps(state))
        
        monitor_path = plugin_path / "src" / "hooks" / "post_tool_monitor.py"
        
        def run_hook(payload):
            env = {**os.environ, "PYTHONPATH": str(plugin_path / "src")}
            res = subprocess.run(
                [sys.executable, str(monitor_path)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                env=env
            )
            if res.stderr:
                print(f"HOOK STDERR: {res.stderr}")
            return res

        # 1. Verify Fix 1: MultiEdit support
        qa_report = tmp_project / "artifacts" / "qa_report.md"
        qa_report.write_text("<QA_METADATA>\n{\"status\": \"FAIL\"}\n</QA_METADATA>")
        
        payload_multiedit = {
            "tool_name": "MultiEdit",
            "tool_args": {"edits": [{"file_path": "artifacts/qa_report.md", "old_string": "...", "new_string": "..."}]}
        }
        
        run_hook(payload_multiedit)
        with open(state_file, "r") as f:
            new_state = json.load(f)
            print(f"DEBUG: consecutive_failures after MultiEdit: {new_state['consecutive_failures']}")
            assert new_state["consecutive_failures"] == 2 

        # 2. Verify Fix 2: Robust failure detection (whitespace/quotes)
        qa_report.write_text("<QA_METADATA>\n{ 'status' :  'FAIL' }\n</QA_METADATA>")
        payload_write = {
            "tool_name": "write_file",
            "tool_args": {"file_path": "artifacts/qa_report.md"}
        }
        run_hook(payload_write)
        with open(state_file, "r") as f:
            new_state = json.load(f)
            print(f"DEBUG: consecutive_failures after robust match: {new_state['consecutive_failures']}")
            assert new_state["consecutive_failures"] == 3
            assert new_state["locked"] is True

        # 3. Verify Fix 3: Robust reset logic (Only reset on PASS)
        # Manually reset and unlock for testing
        new_state["consecutive_failures"] = 2
        new_state["locked"] = False
        state_file.write_text(json.dumps(new_state))
        
        # Also remove DB to force reload from JSON
        db_file = config_dir / "harness.db"
        if db_file.exists():
            db_file.unlink()
        
        # Intermediate write - should NOT reset
        qa_report.write_text("Just some text, neither PASS nor FAIL")
        run_hook(payload_write)
        with open(state_file, "r") as f:
            new_state = json.load(f)
            print(f"DEBUG: consecutive_failures after intermediate write: {new_state['consecutive_failures']}")
            assert new_state["consecutive_failures"] == 2

        # Success write - SHOULD reset
        qa_report.write_text("<QA_METADATA>\n{\"status\": \"PASS\"}\n</QA_METADATA>")
        run_hook(payload_write)
        with open(state_file, "r") as f:
            new_state = json.load(f)
            print(f"DEBUG: consecutive_failures after PASS: {new_state['consecutive_failures']}")
            assert new_state["consecutive_failures"] == 0

if __name__ == "__main__":
    test_autonomous_recovery_fixes_verification()
    print("ALL VERIFICATIONS PASSED!")
