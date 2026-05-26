import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from harness.init.minting_engine import wait_for_user_review_and_read_domain

class TestHeadlessMode(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.doc_path = os.path.join(self.test_dir, "ONBOARDING_DOMAIN.md")
        with open(self.doc_path, "w") as f:
            f.write("Some domain content")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('builtins.input', side_effect=AssertionError("input() called in headless mode!"))
    @patch.dict(os.environ, {"HARNESS_HEADLESS": "1"})
    def test_minting_engine_headless(self, mock_input):
        # This should NOT call input() and should return the content
        content = wait_for_user_review_and_read_domain(self.test_dir)
        self.assertEqual(content, "Some domain content")
        mock_input.assert_not_called()

    @patch('builtins.input', side_effect=AssertionError("input() called in headless mode!"))
    @patch.dict(os.environ, {"HARNESS_HEADLESS": "1"})
    def test_minting_engine_headless_with_placeholder(self, mock_input):
        # Even with placeholders, it should just return the content in headless mode
        with open(self.doc_path, "w") as f:
            f.write("Some domain content with [USER INPUT REQUIRED]")
        
        content = wait_for_user_review_and_read_domain(self.test_dir)
        self.assertEqual(content, "Some domain content with [USER INPUT REQUIRED]")
        mock_input.assert_not_called()

    @patch('builtins.input', return_value="Some input")
    @patch.dict(os.environ, {}, clear=True)
    def test_minting_engine_interactive(self, mock_input):
        # This SHOULD call input()
        content = wait_for_user_review_and_read_domain(self.test_dir)
        self.assertEqual(content, "Some domain content")
        self.assertTrue(mock_input.called)

if __name__ == "__main__":
    unittest.main()
