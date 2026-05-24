import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
from harness.cli import main

class TestInteractiveCLI(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        import subprocess
        subprocess.run(["git", "init"], cwd=self.test_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('harness.cli.parse_args')
    @patch('harness.discovery_engine.acquire_mcp_context', return_value="fake context")
    @patch('harness.cli.getpass.getpass', return_value="fake-key")
    @patch('builtins.input')
    @patch('harness.discovery_engine.generate_grilling_questions')
    @patch('harness.discovery_engine.synthesize_grilled_context')
    @patch('subprocess.run')
    @patch('sys.exit')
    @patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key"})
    def test_cli_interactive_grilling(self, mock_exit, mock_run, mock_synth, mock_gen, mock_input, mock_getpass, mock_acquire, mock_parse_args):
        # We need to remove HARNESS_HEADLESS from env if it exists
        if "HARNESS_HEADLESS" in os.environ:
            del os.environ["HARNESS_HEADLESS"]

        args = MagicMock()
        args.project_path = self.test_dir
        args.llm = "gemini"
        args.model = None
        args.bundle = None
        mock_parse_args.return_value = args

        mock_gen.return_value = [
            {"question": "Is this a Flask app?", "multiple_choice_options": ["Yes", "No"]},
            {"question": "What is the domain?", "multiple_choice_options": []},
            {"question": "What is the DB?", "multiple_choice_options": ["Postgres", "MySQL"]}
        ]
        
        # Inputs:
        # 1. Answer to "Is this a Flask app?" -> 'A' (mapped to Yes)
        # 2. Answer to "What is the domain?" -> 'Fintech' (no options, open input)
        # 3. Answer to "What is the DB?" -> 'C' (Other), then 'MongoDB'
        # 4. Answer to "Select target platform" -> '1'
        mock_input.side_effect = ["A", "Fintech", "C", "MongoDB", "1"]
        
        mock_synth.return_value = "# Project Context\n\n## Purpose\nA Fintech Flask app with MongoDB."

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
        
        # Verify generate_grilling_questions was called
        mock_gen.assert_called_once()
        
        # Verify synthesize_grilled_context was called with correct QA pairs
        mock_synth.assert_called_once()
        args_list = mock_synth.call_args[0]
        qa_pairs = args_list[1]
        self.assertEqual(qa_pairs[0], ("Is this a Flask app?", "Yes"))
        self.assertEqual(qa_pairs[1], ("What is the domain?", "Fintech"))
        self.assertEqual(qa_pairs[2], ("What is the DB?", "MongoDB"))

        # Verify CONTEXT.md was created with synth output
        context_file = os.path.join(self.test_dir, "docs", "domain", "CONTEXT.md")
        self.assertTrue(os.path.exists(context_file))
        with open(context_file, 'r') as f:
            content = f.read()
            self.assertIn("A Fintech Flask app with MongoDB.", content)

if __name__ == "__main__":
    unittest.main()
