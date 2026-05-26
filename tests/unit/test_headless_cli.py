import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
import sys
from io import StringIO

from harness.init.cli import HarnessSetupError, main

class TestHeadlessCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        import subprocess
        subprocess.run(["git", "init"], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('harness.init.cli.parse_args')
    @patch('builtins.input', side_effect=AssertionError("input() called in headless mode!"))
    @patch('subprocess.run')
    @patch('sys.exit')
    @patch.dict(os.environ, {"HARNESS_HEADLESS": "1"})
    def test_cli_headless(self, mock_exit, mock_run, mock_input, mock_parse_args):
        args = MagicMock()
        args.project_path = self.test_dir
        args.bundle = None
        mock_parse_args.return_value = args

        with patch('harness.init.minting_engine.mint_workspace'):
            try:
                main()
            except SystemExit:
                pass
        
        mock_input.assert_not_called()

    @patch('harness.init.cli.parse_args')
    @patch('builtins.input', side_effect=AssertionError("input() called in headless mode!"))
    @patch('subprocess.run')
    @patch('sys.exit')
    @patch.dict(os.environ, {"HARNESS_HEADLESS": "1"})
    def test_cli_headless_fails_when_embedded_setup_fails(self, mock_exit, mock_run, mock_input, mock_parse_args):
        args = MagicMock()
        args.project_path = self.test_dir
        args.bundle = None
        mock_parse_args.return_value = args

        with patch('harness.init.minting_engine.mint_workspace'), \
             patch('harness.init.cli.run_embedded_setup', side_effect=HarnessSetupError("boom")):
            try:
                main()
            except SystemExit:
                pass

        mock_exit.assert_called_with(1)

    @patch('harness.init.cli.parse_args')
    @patch('builtins.input')
    @patch('subprocess.run')
    @patch('sys.exit')
    @patch.dict(os.environ, clear=True)
    def test_cli_claude_plugin_generation(self, mock_exit, mock_run, mock_input, mock_parse_args):
        args = MagicMock()
        args.project_path = self.test_dir
        args.bundle = None
        mock_parse_args.return_value = args

        # Select target platform 2 (Claude)
        mock_input.side_effect = ["2"]

        with patch('harness.init.minting_engine.mint_workspace'), \
             patch('harness.init.plugin_generator.generate_orchestrator_plugin') as mock_gen_plugin:
            try:
                main()
            except SystemExit:
                pass
            
            # Since we chose Claude (2), plugin generation must be called!
            mock_gen_plugin.assert_called_once()

if __name__ == "__main__":
    unittest.main()