import unittest
from pathlib import Path
import tempfile
import json
import os
from unittest.mock import MagicMock, patch
from tests.sandbox.runner import ToolExecutionEngine, MockHost, run_scenario, RoutingResult

class TestSandboxRunner(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp_dir.name)
        self.tool_engine = ToolExecutionEngine(self.workspace)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_tool_read_write(self):
        self.tool_engine.write_file("test.txt", "hello world")
        content = self.tool_engine.read_file("test.txt")
        self.assertEqual(content, "hello world")

    def test_tool_replace(self):
        self.tool_engine.write_file("test.txt", "hello world")
        self.tool_engine.replace("test.txt", "world", "sandbox")
        content = self.tool_engine.read_file("test.txt")
        self.assertEqual(content, "hello sandbox")

    def test_tool_grep(self):
        self.tool_engine.write_file("test.txt", "hello world\ngoodbye world")
        result = self.tool_engine.grep_search("goodbye")
        self.assertIn("goodbye world", result)

    @patch("tests.sandbox.runner.query_llm")
    @patch("tests.sandbox.runner.mint_harness")
    def test_mock_host_loop(self, mock_mint, mock_query):
        # Setup mock project
        (self.workspace / "app.py").write_text("def hello(): pass")
        
        # Mock LLM responses
        mock_query.side_effect = [
            '{"name": "Task", "arguments": {"agent_name": "implementer", "prompt": "fix it"}}',
            '{"name": "Read", "arguments": {"file_path": "app.py"}}',
            'I am done'
        ]
        
        # Mock plugin directory and root hooks
        plugin_dir = self.workspace / ".claude" / "harness-wf-plugin"
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        
        # Create dummy hooks that just return success
        for hook in ["prompt_classifier", "pre_tool_guard", "post_tool_observer"]:
            (hooks_dir / f"{hook}.py").write_text("import sys; print('success')")

        # Mock OrchestratorDispatcher
        mock_dispatcher = MagicMock()
        mock_dispatcher.agents_config = {"agents": {"implementer": {"source": "You are implementer"}}}
        mock_dispatcher.rules_config = {"rules": {}}
        mock_dispatcher._load_state.return_value = {}
        
        with patch("tests.sandbox.runner.OrchestratorDispatcher", return_value=mock_dispatcher):
            host = MockHost(self.workspace, "fake-key")
            host.run_task("Add docstring")
            
            # Check history: User, Assistant(Task), User(Task result), Assistant(Read), User(Read result), Assistant(done)
            self.assertEqual(len(host.history), 6)
            # Let me re-verify the loop logic.

class TestRunScenario(unittest.TestCase):
    """Tests for the programmatic run_scenario entry point."""

    def _make_fake_plugin_root(self, tmp_path: Path) -> Path:
        """Build a minimal plugin_root directory with enough config for the dispatcher."""
        plugin_root = tmp_path / "harness-wf-plugin"
        config_dir = plugin_root / "config"
        config_dir.mkdir(parents=True)

        # Minimal agents.json — dispatcher requires at least an "agents" key
        (config_dir / "agents.json").write_text(
            json.dumps({"agents": {"orchestrator": {"source": "You are orchestrator"}}})
        )
        # Minimal rules.json
        (config_dir / "rules.json").write_text(json.dumps({"rules": {}}))
        # No orchestrator.json needed — dispatcher returns {} if missing
        return plugin_root

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_run_scenario_returns_routing_result(self):
        """run_scenario returns a RoutingResult with branch, skill, agent fields."""
        plugin_root = self._make_fake_plugin_root(self.tmp_path)

        # Use the captured routing-miss scenario: rename task -> should route to D
        scenario = {
            "name": "rename_test",
            "prompt": "Rename LoginComponent to AuthComponent everywhere in the codebase",
            "expected_behavior": {"branch": "D", "agent": "implementer"},
        }

        # Patch classify_intent to return deterministic result (no LLM call)
        with patch(
            "harness.runtime.dispatcher.OrchestratorDispatcher.classify_intent",
            return_value={"branch": "D", "justification": "test"},
        ):
            result = run_scenario(plugin_root, scenario)

        self.assertIsInstance(result, RoutingResult)
        self.assertEqual(result.branch, "D")
        self.assertEqual(result.agent, "implementer")
        self.assertEqual(result.skill, "harness-test-driven-development")

    def test_run_scenario_branch_c(self):
        """run_scenario correctly propagates branch C routing (no skill, generalist agent)."""
        plugin_root = self._make_fake_plugin_root(self.tmp_path)

        scenario = {
            "name": "question_test",
            "prompt": "How does the dispatcher classify intents?",
        }

        with patch(
            "harness.runtime.dispatcher.OrchestratorDispatcher.classify_intent",
            return_value={"branch": "C", "justification": "test"},
        ):
            result = run_scenario(plugin_root, scenario)

        self.assertIsInstance(result, RoutingResult)
        self.assertEqual(result.branch, "C")
        self.assertIsNone(result.skill)
        self.assertEqual(result.agent, "generalist")

    def test_routing_result_fields(self):
        """RoutingResult exposes branch, skill, and agent attributes."""
        r = RoutingResult(branch="A", skill="harness-systematic-debugging", agent="debugger")
        self.assertEqual(r.branch, "A")
        self.assertEqual(r.skill, "harness-systematic-debugging")
        self.assertEqual(r.agent, "debugger")


if __name__ == "__main__":
    unittest.main()
