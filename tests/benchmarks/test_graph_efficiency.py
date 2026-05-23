import os
import sys
import json
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

# MockTokenCounter implementation
class MockTokenCounter:
    def __init__(self):
        self.total_tokens = 0
        self.log = []

    def record_mcp_codegraph(self, tool_name):
        cost = 100
        self.total_tokens += cost
        self.log.append(f"Call {tool_name}: {cost} tokens")

    def record_grep_search(self, output):
        cost = len(output) // 4
        self.total_tokens += cost
        self.log.append(f"Call grep_search ({len(output)} chars): {cost} tokens")

    def record_read_file(self, content):
        cost = len(content) // 4
        self.total_tokens += cost
        self.log.append(f"Call read_file ({len(content)} chars): {cost} tokens")

    def get_summary(self):
        return "\n".join(self.log) + f"\nTotal: {self.total_tokens} tokens"

class TestGraphEfficiency(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.src_dir = self.temp_dir / "src"
        self.hooks_dir = self.src_dir / "hooks"
        self.config_dir = self.temp_dir / "config"
        
        self.hooks_dir.mkdir(parents=True)
        self.config_dir.mkdir()
        
        # Copy necessary files from the project
        project_root = Path(__file__).parent.parent.parent
        shutil.copy(project_root / "src" / "harness" / "database.py", self.src_dir / "database.py")
        shutil.copy(project_root / "src" / "harness" / "dispatcher.py", self.src_dir / "dispatcher.py")
        
        # Generate hooks using the templates from plugin_generator.py (simplified)
        self._generate_hooks()
        
        # Setup initial state
        self._set_state({
            "setup_complete": True,
            "strict_enforcement_enabled": True,
            "active_persona": "implementer"
        })

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _set_state(self, state):
        # We need to use OrchestratorDispatcher to save state so it goes to the DB correctly
        sys.path.insert(0, str(self.src_dir))
        from dispatcher import OrchestratorDispatcher
        dispatcher = OrchestratorDispatcher(str(self.config_dir))
        dispatcher._save_state(state)
        sys.path.pop(0)

    def _get_state(self):
        sys.path.insert(0, str(self.src_dir))
        from dispatcher import OrchestratorDispatcher
        dispatcher = OrchestratorDispatcher(str(self.config_dir))
        state = dispatcher._load_state()
        sys.path.pop(0)
        return state

    def _generate_hooks(self):
        # Hook header (simplified)
        hook_header = f"""import sys, os; sys.path.insert(0, '{self.src_dir}')
import datetime
import json
from pathlib import Path
from dispatcher import OrchestratorDispatcher

def log_action(hook_name, action, details=""):
    config_dir = '{self.config_dir}'
    log_file = os.path.join(config_dir, 'harness.log')
    timestamp = datetime.datetime.now().isoformat()
    pid = os.getpid()
    try:
        with open(log_file, 'a') as f:
            f.write(f"[{{timestamp}}] [PID:{{pid}}] [{{hook_name}}] {{action}} - {{details}}\\n")
    except Exception:
        pass

def load_dispatcher():
    return OrchestratorDispatcher('{self.config_dir}')

def read_hook_payload():
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {{"raw": raw}}
    if len(sys.argv) > 1:
        return {{"tool_name": sys.argv[1], "tool_args": sys.argv[2] if len(sys.argv) > 2 else ""}}
    return {{}}

def extract_tool(payload):
    tool_name = payload.get("tool_name") or ""
    tool_args = payload.get("tool_args") or {{}}
    return str(tool_name), tool_args

def stringify(value):
    if isinstance(value, str): return value
    return json.dumps(value)

def setup_ready(state):
    return bool(state.get("setup_complete") and state.get("strict_enforcement_enabled"))
"""

        pre_tool_guard_content = hook_header + """
import re

def is_grep_command(command):
    return bool(re.search(r"(^|\\s)(grep|rg)(\\s|$)", command))

def is_large_read(tool_args):
    if not isinstance(tool_args, dict): return False
    limit = tool_args.get("limit") or tool_args.get("size") or 0
    try: return int(limit) > 20000
    except: return False

def reject(dispatcher, state, message):
    print(message, file=sys.stderr)
    sys.exit(1)

def check_tool_use(tool_name, tool_args):
    dispatcher = load_dispatcher()
    state = dispatcher._load_state()
    tool_text = stringify(tool_args)
    if not setup_ready(state): return True

    if tool_name in {"Bash", "run_shell_command"} and is_grep_command(tool_text) and not state.get("last_codegraph_use_at"):
        reject(dispatcher, state, "[EFFICIENCY VIOLATION]: Graph-First Strategy strictly enforced. Query CodeGraph MCP before using grep.")
        
    if tool_name in {"Read", "read_file"} and is_large_read(tool_args) and not state.get("last_codegraph_use_at"):
        reject(dispatcher, state, "[EFFICIENCY VIOLATION]: Use CodeGraph before massive Read calls.")
    return True

if __name__ == "__main__":
    payload = read_hook_payload()
    tool_name, tool_args = extract_tool(payload)
    check_tool_use(tool_name, tool_args)
"""
        (self.hooks_dir / "pre_tool_guard.py").write_text(pre_tool_guard_content)

        post_tool_monitor_content = hook_header + """
def record_tool_result(payload):
    dispatcher = load_dispatcher()
    state = dispatcher._load_state()
    tool_name, tool_args = extract_tool(payload)
    now = datetime.datetime.now().isoformat()

    if "codegraph" in tool_name.lower():
        state["last_codegraph_use_at"] = now
        state["last_codegraph_tool"] = tool_name
    
    dispatcher._save_state(state)
    return True

if __name__ == "__main__":
    record_tool_result(read_hook_payload())
"""
        (self.hooks_dir / "post_tool_monitor.py").write_text(post_tool_monitor_content)

    def run_hook(self, hook_name, payload):
        hook_path = self.hooks_dir / f"{hook_name}.py"
        process = subprocess.Popen(
            [sys.executable, str(hook_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=json.dumps(payload))
        return process.returncode, stdout, stderr

    def test_efficiency_comparison(self):
        project_root = Path(__file__).parent.parent.parent
        boilerplate_dir = project_root / "tests" / "fixtures" / "boilerplates" / "sample-py-app"

        # Scenario A (Optimal)
        counter_a = MockTokenCounter()
        counter_a.record_mcp_codegraph("mcp_codegraph_search")
        
        # Simulate reading 20 lines of code from boilerplate
        app_py = boilerplate_dir / "src" / "app.py"
        with open(app_py, "r") as f:
            lines = f.readlines()
            # In a real scenario, graph search gives you exactly the 20 lines you need
            content_20_lines = "".join(lines[:20])
            counter_a.record_read_file(content_20_lines)
        
        # Scenario B (Sub-optimal)
        counter_b = MockTokenCounter()
        # Run a broad grep (searching for "e" to get many results)
        grep_cmd = ["grep", "-r", "e", str(boilerplate_dir)]
        grep_output = subprocess.check_output(grep_cmd, text=True, stderr=subprocess.DEVNULL)
        counter_b.record_grep_search(grep_output)
        
        # Read 3 whole files
        files_to_read = [
            boilerplate_dir / "src" / "app.py",
            boilerplate_dir / "tests" / "test_app.py",
            boilerplate_dir / "pyproject.toml"
        ]
        for f_path in files_to_read:
            if f_path.exists():
                with open(f_path, "r") as f:
                    counter_b.record_read_file(f.read())

        # Scenario C (CodeGraph Failure - Fallback Cost)
        counter_c = MockTokenCounter()
        # Harness enforces Graph-First, so we MUST call it first
        counter_c.record_mcp_codegraph("mcp_codegraph_search")
        # Assume it returns NOTHING (Empty Results)
        # Agent then executes the Grep Scenario (Scenario B) as fallback
        counter_c.record_grep_search(grep_output)
        for f_path in files_to_read:
            if f_path.exists():
                with open(f_path, "r") as f:
                    counter_c.record_read_file(f.read())
        
        print("\nScenario A (Optimal - Graph-First):")
        print(counter_a.get_summary())
        print("\nScenario B (Sub-optimal - Grep/Read):")
        print(counter_b.get_summary())
        print("\nScenario C (CodeGraph Failure - Fallback Cost):")
        print(counter_c.get_summary())
        
        efficiency_gain = counter_b.total_tokens / counter_a.total_tokens if counter_a.total_tokens > 0 else 0
        efficiency_penalty = counter_c.total_tokens - counter_b.total_tokens
        print(f"\nEfficiency Gain (A vs B): {efficiency_gain:.1f}x")
        print(f"Efficiency Penalty (C vs B): {efficiency_penalty} tokens")
        
        # Save report to artifacts
        artifacts_dir = project_root / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        report_path = artifacts_dir / "token_efficiency_report.md"
        with open(report_path, "w") as f:
            f.write("# Token Efficiency Report\n\n")
            f.write("## Scenario A (Optimal - Graph-First Success)\n")
            f.write("```\n" + counter_a.get_summary() + "\n```\n\n")
            f.write("## Scenario B (No Harness - Raw Grep/Read)\n")
            f.write("```\n" + counter_b.get_summary() + "\n```\n\n")
            f.write("## Scenario C (Harness - CodeGraph Failure + Fallback)\n")
            f.write("```\n" + counter_c.get_summary() + "\n```\n\n")
            
            f.write(f"### Results Comparison\n")
            f.write(f"- **Efficiency Gain (A vs B):** {efficiency_gain:.1f}x reduction in tokens when Graph search succeeds.\n")
            f.write(f"- **Efficiency Penalty (C vs B):** {efficiency_penalty} tokens overhead when Graph search fails.\n\n")
            
            f.write("## Adversarial Assessment\n")
            f.write("While the harness *enforces* the Graph-First strategy to maximize efficiency, this strategy relies on CodeGraph being accurate and comprehensive. ")
            f.write("If CodeGraph returns no results or fails, the harness inadvertently increases token overhead by forcing a failed search (Scenario C) before allowing fallback methods. ")
            f.write("The cost of failure is fixed at the cost of the initial CodeGraph query (100 tokens in this benchmark).\n")

        # Even with small files, broad grep and reading full files should be more expensive
        self.assertGreater(efficiency_gain, 1.0)
        self.assertEqual(counter_c.total_tokens, counter_b.total_tokens + 100)

    def test_mandate_enforcement(self):
        # 1. Call pre_tool_guard.py with a grep_search BEFORE any codegraph call.
        payload_grep = {"tool_name": "run_shell_command", "tool_args": "grep -r 'something' ."}
        exit_code, stdout, stderr = self.run_hook("pre_tool_guard", payload_grep)
        
        # Assert: The hook should reject the call with [EFFICIENCY VIOLATION] and exit with 1.
        print(f"Grep before codegraph exit code: {exit_code}")
        print(f"Grep before codegraph stderr: {stderr}")
        self.assertEqual(exit_code, 1)
        self.assertIn("[EFFICIENCY VIOLATION]", stderr)
        self.assertIn("Graph-First Strategy strictly enforced", stderr)

        # 2. Simulate a codegraph call via post_tool_monitor.py.
        payload_codegraph = {"tool_name": "mcp_codegraph_search", "tool_args": {"query": "something"}}
        exit_code, stdout, stderr = self.run_hook("post_tool_monitor", payload_codegraph)
        self.assertEqual(exit_code, 0)
        
        # Verify state updated
        state = self._get_state()
        self.assertIn("last_codegraph_use_at", state)

        # 3. Call pre_tool_guard.py again with the same grep payload.
        exit_code, stdout, stderr = self.run_hook("pre_tool_guard", payload_grep)
        
        # Assert: The hook should now allow the call (exit 0).
        print(f"Grep after codegraph exit code: {exit_code}")
        self.assertEqual(exit_code, 0)

    def test_large_read_enforcement(self):
        # 1. Call pre_tool_guard.py with a large read_file BEFORE any codegraph call.
        payload_read = {"tool_name": "read_file", "tool_args": {"path": "large_file.py", "limit": 25000}}
        exit_code, stdout, stderr = self.run_hook("pre_tool_guard", payload_read)
        
        self.assertEqual(exit_code, 1)
        self.assertIn("[EFFICIENCY VIOLATION]", stderr)
        self.assertIn("Use CodeGraph before massive Read calls", stderr)

        # 2. Simulate a codegraph call via post_tool_monitor.py.
        payload_codegraph = {"tool_name": "mcp_codegraph_search", "tool_args": {"query": "something"}}
        self.run_hook("post_tool_monitor", payload_codegraph)
        
        # 3. Call pre_tool_guard.py again with the same read payload.
        exit_code, stdout, stderr = self.run_hook("pre_tool_guard", payload_read)
        self.assertEqual(exit_code, 0)

if __name__ == "__main__":
    unittest.main()
