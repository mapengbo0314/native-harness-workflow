import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from harness.cli import main
from harness.utils import get_boilerplate_dir

class TestInitFlow(unittest.TestCase):
    @patch('harness.cli.parse_args')
    @patch('shutil.which')
    @patch('os.environ.get')
    @patch('subprocess.run')
    @patch('builtins.input')
    @patch('getpass.getpass')
    @patch('harness.minting_engine.mint_workspace')
    @patch('harness.minting_engine.wait_for_user_review_and_read_domain')
    @patch('harness.minting_engine.synthesize_domain_sme_agent')
    @patch('harness.minting_engine.patch_orchestrator_rules')
    @patch('harness.minting_engine.parse_tool_checklists')
    @patch('harness.minting_engine.install_workspace_tools')
    @patch('harness.discovery_engine.acquire_mcp_context')
    @patch('harness.discovery_engine.generate_onboarding_domain_doc')
    def test_init_resolves_local_boilerplate(self, 
                                            mock_gen_doc, 
                                            mock_acquire_context, 
                                            mock_install_tools,
                                            mock_parse_checklists,
                                            mock_patch_rules,
                                            mock_synth_sme,
                                            mock_wait_domain,
                                            mock_mint,
                                            mock_getpass,
                                            mock_input,
                                            mock_subrun,
                                            mock_env_get,
                                            mock_which,
                                            mock_parse_args):
        # Setup mocks
        mock_parse_args.return_value = MagicMock(
            command='init',
            project_path='/tmp/test_project',
            llm='gemini',
            model='gemini-1.5-pro'
        )
        mock_which.return_value = '/usr/local/bin/npx'
        mock_env_get.return_value = 'test_api_key'
        mock_acquire_context.return_value = 'some context'
        mock_input.side_effect = ['Purpose', 'Vocab', 'Invariants', '1'] # Gemini CLI choice
        mock_wait_domain.return_value = 'some domain content'
        mock_parse_checklists.return_value = ([], [])
        mock_synth_sme.return_value = 'domain-sme'
        
        # Ensure directories exist
        with patch('os.path.exists', return_value=True):
            with patch('os.makedirs'):
                with patch('builtins.open', unittest.mock.mock_open()):
                    # Run main
                    try:
                        main()
                    except SystemExit:
                        pass
        
        # Verify that mint_workspace was called with the local boilerplate path
        expected_bp_dir = str(get_boilerplate_dir())
        
        # Check if mint_workspace was called
        self.assertTrue(mock_mint.called)
        args, kwargs = mock_mint.call_args
        # mint_workspace(target_dir, selected_agents, args.project_path, platform_choice, args.model, boilerplate_dir)
        self.assertEqual(args[5], expected_bp_dir)
        print(f"Verified: mint_workspace called with boilerplate_dir={args[5]}")

if __name__ == '__main__':
    unittest.main()
