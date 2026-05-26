import unittest
from unittest.mock import patch, MagicMock
import os
import shutil
import tempfile

from harness.init.cli import HarnessSetupError, main

class TestInteractiveCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('harness.init.cli.parse_args')
    @patch('builtins.input')
    @patch('subprocess.run')
    @patch('sys.exit')
    @patch.dict(os.environ, clear=True)
    def test_cli_interactive(self, mock_exit, mock_run, mock_input, mock_parse_args):
        # We need to remove HARNESS_HEADLESS from env if it exists
        if "HARNESS_HEADLESS" in os.environ:
            del os.environ["HARNESS_HEADLESS"]

        args = MagicMock()
        args.project_path = self.test_dir
        args.bundle = None
        mock_parse_args.return_value = args

        # Inputs:
        # 1. Answer to "Select target platform" -> '1'
        mock_input.side_effect = ["1"]

        with patch('harness.init.minting_engine.mint_workspace'):
            try:
                main()
            except SystemExit:
                pass
        
        # Verify input was called 1 times
        self.assertEqual(mock_input.call_count, 1)

if __name__ == "__main__":
    unittest.main()