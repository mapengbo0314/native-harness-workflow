
import os
import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from harness.cli import main

@patch('harness.cli.parse_args')
@patch('harness.cli.os.path.abspath')
@patch('harness.cli.os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('harness.minting_engine.mint_workspace')
@patch('harness.minting_engine.install_workspace_tools')
@patch('harness.minting_engine.synthesize_domain_sme_agent')
@patch('harness.minting_engine.patch_orchestrator_rules')
@patch('harness.minting_engine.wait_for_user_review_and_read_domain')
@patch('harness.discovery_engine.acquire_mcp_context')
@patch('harness.discovery_engine.generate_onboarding_domain_doc')
@patch('harness.cli.subprocess.run')
@patch('builtins.input')
@patch('getpass.getpass')
@patch('shutil.which')
def test_path_normalization_gemini(
    mock_which, mock_getpass, mock_input, mock_run, mock_generate_doc, mock_acquire, 
    mock_wait, mock_patch, mock_synthesize, mock_install, 
    mock_mint, mock_open, mock_makedirs, mock_abspath, mock_parse
):
    # Setup
    args = MagicMock()
    args.project_path = "/root/.gemini"
    args.llm = "gemini"
    args.detailed = False
    args.ddd = False
    mock_parse.return_value = args
    
    mock_abspath.side_effect = lambda x: x # Keep it simple
    mock_input.side_effect = ["Purpose", "Vocab", "Invariants", "1"] # Platform Choice 1 (Gemini)
    mock_getpass.return_value = "fake-key"
    mock_wait.return_value = "domain content"
    
    # Run
    with patch('os.environ', {"GEMINI_API_KEY": "fake-key"}):
        with patch('os.path.exists', return_value=True):
            main()
            
    # Verify backtracking
    # args.project_path should have been changed to "/root"
    assert args.project_path == "/root"
    
    # Target dir should be "/root/.gemini"
    mock_mint.assert_called_once()
    actual_target_dir = mock_mint.call_args[0][0]
    assert actual_target_dir == "/root/.gemini"

@patch('harness.cli.parse_args')
@patch('harness.cli.os.path.abspath')
@patch('harness.cli.os.makedirs')
@patch('builtins.open', new_callable=mock_open)
@patch('harness.minting_engine.mint_workspace')
@patch('harness.minting_engine.install_workspace_tools')
@patch('harness.minting_engine.synthesize_domain_sme_agent')
@patch('harness.minting_engine.patch_orchestrator_rules')
@patch('harness.minting_engine.wait_for_user_review_and_read_domain')
@patch('harness.discovery_engine.acquire_mcp_context')
@patch('harness.discovery_engine.generate_onboarding_domain_doc')
@patch('harness.cli.subprocess.run')
@patch('builtins.input')
@patch('getpass.getpass')
@patch('shutil.which')
def test_path_normalization_no_nesting_needed(
    mock_which, mock_getpass, mock_input, mock_run, mock_generate_doc, mock_acquire, 
    mock_wait, mock_patch, mock_synthesize, mock_install, 
    mock_mint, mock_open, mock_makedirs, mock_abspath, mock_parse
):
    # Setup
    args = MagicMock()
    args.project_path = "/root"
    args.llm = "gemini"
    args.detailed = False
    args.ddd = False
    mock_parse.return_value = args
    
    mock_abspath.side_effect = lambda x: x
    mock_input.side_effect = ["Purpose", "Vocab", "Invariants", "1"]
    mock_getpass.return_value = "fake-key"
    mock_wait.return_value = "domain content"
    
    # Run
    with patch('os.environ', {"GEMINI_API_KEY": "fake-key"}):
        with patch('os.path.exists', return_value=True):
            main()
            
    # Verify no backtracking
    assert args.project_path == "/root"
    
    # Target dir should be "/root/.gemini"
    mock_mint.assert_called_once()
    actual_target_dir = mock_mint.call_args[0][0]
    assert actual_target_dir == "/root/.gemini"
