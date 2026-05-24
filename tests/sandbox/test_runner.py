import unittest
from pathlib import Path
import tempfile
import json
import os
from unittest.mock import MagicMock, patch
from tests.sandbox.runner import ToolExecutionEngine, MockHost

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
        plugin_dir = self.workspace / ".claude" / "plugin-generated"
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        
        # Create dummy hooks that just return success
        for hook in ["prompt_classifier", "pre_tool_guard", "post_tool_observer", "stop_verifier"]:
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

if __name__ == "__main__":
    unittest.main()
