import json
import sys
import os
import subprocess
import shutil
import tempfile
from pathlib import Path

def run_hook(hook_script: str, input_data: dict, tmp_dir: Path) -> dict:
    project_root = Path(__file__).parent.parent.parent
    hook_path = project_root / "src/harness/templates/boilerplate/hooks" / hook_script
    env = {
        "PYTHONPATH": str(project_root / "src/harness/templates/boilerplate/hooks"),
        "PATH": os.environ.get("PATH", "")
    }
    
    # Use input_data as the mock state json input to override root
    input_data["workspace_root"] = str(tmp_dir)
    
    process = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(input_data),
        text=True,
        capture_output=True,
        env=env,
        cwd=tmp_dir
    )
    
    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }

def test_prompt_classifier():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_data = {"prompt": "Fix this bug"}
        res = run_hook("prompt_classifier.py", input_data, tmp_path)
        assert res["returncode"] == 0
        assert "Branch A" in res["stdout"]

def test_pre_tool_guard():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_data = {
            "toolName": "Write",
            "toolInput": {"path": ".claude/settings.json"}
        }
        res = run_hook("pre_tool_guard.py", input_data, tmp_path)
        assert res["returncode"] == 2
        assert "blocked" in res["stderr"].lower()
        
        # Test pass case
        input_data = {
            "toolName": "Write",
            "toolInput": {"path": "src/app.py"}
        }
        res = run_hook("pre_tool_guard.py", input_data, tmp_path)
        assert res["returncode"] == 0
        assert "allow" in res["stdout"]
        
        # Test Branch D planner/verifier escalation blocked
        state_dir = tmp_path / "state"
        state_dir.mkdir(exist_ok=True)
        (state_dir / "campaign_state.json").write_text('{"current_branch": "Branch D"}')
        input_data = {
            "toolName": "Task",
            "toolInput": "Please ask the planner to do this"
        }
        res = run_hook("pre_tool_guard.py", input_data, tmp_path)
        assert res["returncode"] == 2
        assert "blocked" in res["stderr"].lower()

        # Test Branch D explicit override allowed
        input_data = {
            "toolName": "Task",
            "toolInput": "Please ask the planner explicit to do this"
        }
        res = run_hook("pre_tool_guard.py", input_data, tmp_path)
        assert res["returncode"] == 0
        assert "allow" in res["stdout"]

def test_config_change_guard():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_data = {"changes": []}
        res = run_hook("config_change_guard.py", input_data, tmp_path)
        assert res["returncode"] == 2
        
        # Test success case
        state_dir = tmp_path / "state"
        state_dir.mkdir(exist_ok=True)
        (state_dir / "campaign_state.json").write_text('{"maintenance_mode": true}')
        res = run_hook("config_change_guard.py", input_data, tmp_path)
        assert res["returncode"] == 0

def test_stop_verifier():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        mock_script = scripts_dir / "verify_contract.py"
        mock_script.write_text("import sys\nprint('Verification failed')\nsys.exit(1)\n")
        
        input_data = {}
        res = run_hook("stop_verifier.py", input_data, tmp_path)
        assert res["returncode"] == 2
        assert "verification failed" in res["stderr"].lower()
        
        # Test success case
        mock_script.write_text("import sys\nprint('Verification passed')\nsys.exit(0)\n")
        res = run_hook("stop_verifier.py", input_data, tmp_path)
        assert res["returncode"] == 0

def test_precompact_handoff():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_data = {}
        res = run_hook("precompact_handoff.py", input_data, tmp_path)
        assert res["returncode"] == 0
        assert (tmp_path / "HANDOFF.md").exists()

def test_post_tool_observer():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_data = {"error": "Failed"}
        res = run_hook("post_tool_observer.py", input_data, tmp_path)
        assert res["returncode"] == 0
