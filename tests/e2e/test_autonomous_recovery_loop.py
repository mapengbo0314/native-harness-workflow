import os
import json
import pytest
import tempfile
from pathlib import Path
import sys
import subprocess

# Add project root and src to sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from tests.sandbox.runner import MockHost, mint_harness

class AutonomousRecoveryMockHost(MockHost):
    def __init__(self, workspace_root, dry_run_turns):
        super().__init__(workspace_root, api_key="mock", dry_run=True)
        self.dry_run_turns = dry_run_turns

    def run_hook(self, hook_module: str, input_data: dict) -> str:
        """Run a hook via subprocess to simulate real Claude Code behavior."""
        hook_path = self.plugin_dir / "src" / "hooks" / f"{hook_module}.py"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.plugin_dir / "src")
        
        proc = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(input_data),
            env=env,
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
             return f"HOOK_REJECTION: {proc.stderr}"
        return proc.stdout.strip()

    def run_task(self, user_prompt: str):
        # We need to ensure state is initialized as setup_ready
        state = self.dispatcher._load_state()
        state["setup_complete"] = True
        state["strict_enforcement_enabled"] = True
        self.dispatcher._save_state(state)
        
        # Override dry_run_turns logic
        self.history.append({"role": "user", "content": user_prompt})
        
        try:
            for turn in range(len(self.dry_run_turns)):
                print(f"--- Turn {turn+1} ---")
                response_text = self.dry_run_turns[turn]
                
                self.logger.log_event("LLM_RESPONSE", {"text": response_text})
                tool_calls = self._parse_tool_calls(response_text)
                
                if tool_calls:
                    self.history.append({"role": "assistant", "content": response_text})
                    for tool_call in tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["arguments"]
                        
                        # Run pre_tool_guard
                        guard_result = self.run_hook("pre_tool_guard", {
                            "tool_name": tool_name,
                            "tool_args": tool_args
                        })
                        
                        if guard_result.startswith("HOOK_REJECTION:"):
                            print(f"Guard Rejected: {guard_result}")
                            self.history.append({"role": "user", "content": guard_result})
                            continue
                        
                        # Execute tool
                        tool_result = self._execute_tool(tool_name, tool_args)
                        
                        # Run post_tool_monitor
                        self.run_hook("post_tool_monitor", {
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "result": tool_result
                        })
                        
                        self.history.append({"role": "user", "content": f"Tool Result ({tool_name}): {json.dumps(tool_result)}"})
                else:
                    self.history.append({"role": "assistant", "content": response_text})
        finally:
            print("--- Task Finished ---")

def test_autonomous_recovery_loop():
    """
    E2E Test: Verify the 3-strike rule locks the system after 3 consecutive verification failures.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        workspace = Path(tmp_dir)
        
        # 1. Mint harness
        os.environ["HARNESS_HEADLESS"] = "1"
        mint_harness(str(workspace), "RecoveryTestApp")
        
        # Create artifacts directory if not exists (mint_harness should handle basic structure)
        (workspace / "artifacts").mkdir(parents=True, exist_ok=True)
        
        # 2. Define turns that simulate 3 failures and then a blocked attempt
        dry_run_turns = [
            # Turn 1: 1st failure
            '{"tool": "write_file", "arguments": {"file_path": "artifacts/qa_report.md", "content": "{\\"status\\": \\"FAIL\\"}"}}',
            # Turn 2: 2nd failure
            '{"tool": "write_file", "arguments": {"file_path": "artifacts/qa_report.md", "content": "{\\"status\\": \\"FAIL\\"}"}}',
            # Turn 3: 3rd failure
            '{"tool": "write_file", "arguments": {"file_path": "artifacts/qa_report.md", "content": "{\\"status\\": \\"FAIL\\"}"}}',
            # Turn 4: Attempted tool use after lock
            '{"tool": "read_file", "arguments": {"file_path": "docs/domain/CONTEXT.md"}}'
        ]
        
        # 3. Run MockHost
        host = AutonomousRecoveryMockHost(workspace, dry_run_turns)
        host.run_task("Fix the bug and verify it.")
        
        # 4. Verify state
        state_file = workspace / ".claude" / "plugin-generated" / "config" / ".harness_state.json"
        with open(state_file, "r") as f:
            state = json.load(f)
            
        assert state["consecutive_failures"] == 3
        assert state["locked"] is True
        
        # 5. Verify that the last turn was rejected
        # In history, the last entry should be the rejection message
        last_message = host.history[-1]
        assert last_message["role"] == "user"
        assert "HOOK_REJECTION" in last_message["content"]
        assert "Autonomous mode is locked" in last_message["content"]

if __name__ == "__main__":
    test_autonomous_recovery_loop()
    print("E2E Recovery Loop test passed!")
