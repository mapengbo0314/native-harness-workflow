import unittest
from unittest.mock import patch
import sys
from tests.sandbox.runner import main

class TestRunnerArgs(unittest.TestCase):
    @patch('tests.sandbox.runner.setup_scenario_from_data')
    @patch('tests.sandbox.runner.MockHost')
    @patch('tests.sandbox.runner.mint_harness')
    @patch('tempfile.TemporaryDirectory')
    def test_model_flag(self, mock_tempdir, mock_mint, mock_host, mock_setup):
        mock_tempdir.return_value.__enter__.return_value = "/tmp/fake-workspace"
        
        # Simulate running with --model
        test_args = ["runner.py", "--model", "gpt-4-turbo", "--dry-run"]
        with patch.object(sys, 'argv', test_args):
            main()
        
        # Verify MockHost was called with the model
        # We expect main() to pass model to MockHost
        args, kwargs = mock_host.call_args
        self.assertEqual(kwargs.get('model'), "gpt-4-turbo")

if __name__ == "__main__":
    unittest.main()
