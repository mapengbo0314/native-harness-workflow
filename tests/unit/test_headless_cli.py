import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
import sys
from io import StringIO

from harness.cli import main

class TestHeadlessCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Initialize a fake git repo so codegraph init doesn't fail too hard or we mock subprocess.run
        import subprocess
        subprocess.run(["git", "init"], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('harness.cli.parse_args')
    @patch('harness.discovery_engine.acquire_mcp_context', return_value="fake context")
    @patch('harness.cli.getpass.getpass', return_value="fake-key")
    @patch('builtins.input', side_effect=AssertionError("input() called in headless mode!"))
    @patch('subprocess.run')
    @patch('sys.exit')
    @patch.dict(os.environ, {"HARNESS_HEADLESS": "1", "GEMINI_API_KEY": "fake-key"})
    def test_cli_headless(self, mock_exit, mock_run, mock_input, mock_getpass, mock_acquire, mock_parse_args):
        args = MagicMock()
        args.project_path = self.test_dir
        args.llm = "gemini"
        args.model = None
        args.bundle = None
        mock_parse_args.return_value = args

        # Mocking items imported inside main()
        with patch('harness.discovery_engine.generate_onboarding_domain_doc'), \
             patch('harness.minting_engine.wait_for_user_review_and_read_domain', return_value="fake domain"), \
             patch('harness.minting_engine.mint_workspace'), \
             patch('harness.minting_engine.parse_tool_checklists', return_value=([], [])), \
             patch('harness.minting_engine.install_workspace_tools'), \
             patch('harness.minting_engine.synthesize_domain_sme_agent', return_value="fake-sme"), \
             patch('harness.minting_engine.patch_orchestrator_rules'), \
             patch('harness.minting_engine.should_generate_orchestrator_plugin', return_value=False):
            
            try:
                main()
            except SystemExit:
                pass
        
        mock_input.assert_not_called()
        
        # Verify CONTEXT.md was created with defaults
        context_file = os.path.join(self.test_dir, "docs", "domain", "CONTEXT.md")
        self.assertTrue(os.path.exists(context_file))
        with open(context_file, 'r') as f:
            content = f.read()
            self.assertIn("Automated purpose", content)
            self.assertIn("Automated vocab", content)
            self.assertIn("Automated invariants", content)

if __name__ == "__main__":
    unittest.main()
