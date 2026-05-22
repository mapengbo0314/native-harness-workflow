"""
Validator for Claude Code orchestrator hooks.
Tests each hook in isolation with mock payloads.
"""
import json
import subprocess
import sys
import os
from pathlib import Path

def run_hook(hook_name, payload=None, args=None):
    hook_path = Path(__file__).parent / "hooks" / f"{hook_name}.py"
    cmd = [sys.executable, str(hook_path)]
    if args:
        cmd.extend(args)
    
    input_data = json.dumps(payload) if payload else ""
    
    result = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parent)}
    )
    return result

def ensure_harness_state():
    """Ensure the harness state allows for strict enforcement testing."""
    config_dir = Path(__file__).parent.parent / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    state_file = config_dir / ".harness_state.json"
    
    state = {}
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
        except json.JSONDecodeError:
            pass
            
    state["setup_complete"] = True
    state["strict_enforcement_enabled"] = True
    
    with open(state_file, "w") as f:
        json.dump(state, f)

def test_prompt_interceptor():
    print("Testing prompt_interceptor...")
    res = run_hook("prompt_interceptor", payload={"prompt": "build a new login page"})
    if "<matrix_route branch=\"B\">" in res.stdout:
        print("✅ prompt_interceptor OK")
    else:
        print(f"❌ prompt_interceptor FAILED: {res.stdout}")

def test_pre_tool_guard():
    print("Testing pre_tool_guard...")
    # Test rejection of sudo
    res = run_hook("pre_tool_guard", args=["Bash", "sudo rm -rf /"])
    if "[VIOLATION]: sudo" in res.stderr:
        print("✅ pre_tool_guard (sudo rejection) OK")
    else:
        print(f"❌ pre_tool_guard FAILED: {res.stderr}")

def main():
    print("=== Orchestrator Hook Validator ===")
    ensure_harness_state()
    test_prompt_interceptor()
    test_pre_tool_guard()
    # Add more tests as needed

if __name__ == "__main__":
    main()
