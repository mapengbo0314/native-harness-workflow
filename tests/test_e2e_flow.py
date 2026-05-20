import pytest
import os
import json
import shutil
import subprocess
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

from harness.cli import main

# Helper to create a dummy indxr wiki
def setup_dummy_wiki(project_path):
    wiki_path = Path(project_path) / ".indxr" / "wiki"
    wiki_path.mkdir(parents=True, exist_ok=True)
    (wiki_path / "index.md").write_text("# Index\nDummy index content")
    (wiki_path / "architecture.md").write_text("# Architecture\nDummy architecture content")
    return wiki_path

@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@patch('subprocess.run')
@patch('getpass.getpass')
@patch('builtins.input')
@patch('harness.discovery_engine.query_llm')
@patch('harness.discovery_engine.fetch_remote_skill')
@patch('harness.minting_engine.urllib.request.urlopen')
@patch('shutil.which')
def test_e2e_init_flow(
    mock_shutil_which,
    mock_urlopen,
    mock_fetch_remote_skill,
    mock_query_llm,
    mock_input,
    mock_getpass,
    mock_subprocess_run,
    temp_project
):
    """
    E2E Integration Test for harness-wf init.
    Mimics the full interactive onboarding flow including:
    - API key collection
    - DDD alignment grill
    - Agent discovery and selection
    - Custom agent creation
    - Platform selection
    - Phased onboarding (ONBOARDING_DOMAIN.md)
    - Skill and MCP installation
    """
    # 1. Setup mocks
    project_path = temp_project
    mock_shutil_which.side_effect = lambda cmd: f"/usr/local/bin/{cmd}"
    mock_getpass.return_value = "dummy-api-key"
    
    # Mock LLM responses
    def mock_query_llm_side_effect(prompt, llm_provider, api_key, model=None):
        if "Domain-Driven Design architect" in prompt:
            return json.dumps({
                "context_draft": "Dummy DDD context",
                "questions": ["Question 1?", "Question 2?"],
                "legacy_hints": {"Legacy": "Hint"}
            })
        elif "TASK:" in prompt and "specialized agents" in prompt:
            return json.dumps({
                "agents": [
                    {"name": "Agent1", "role": "Role1", "zone": "Core", "system_prompt": "Prompt1"},
                    {"name": "Agent2", "role": "Role2", "zone": "Domain", "system_prompt": "Prompt2"}
                ]
            })
        elif "Agent Architect" in prompt:
            import re
            name_match = re.search(r'Agent Name: (.*)', prompt)
            agent_name = name_match.group(1) if name_match else "CustomAgent"
            return json.dumps({
                "name": agent_name,
                "role": "CustomRole",
                "zone": "Logic",
                "system_prompt": "CustomPrompt"
            })
        elif "Tool Scout" in prompt:
            return json.dumps({
                "tech_stack": "Python, Pytest",
                "skills": [{"name": "fastapi", "url": "https://dummy/fastapi.md"}],
                "mcps": [{"name": "postgres", "command": "npx postgres"}]
            })
        return "{}"

    mock_query_llm.side_effect = mock_query_llm_side_effect
    mock_fetch_remote_skill.return_value = "Dummy skill content"
    
    # Mock urlopen for skill downloading
    mock_response = MagicMock()
    mock_response.read.return_value = b"Dummy remote skill content"
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response
    
    # Mock user inputs
    responses_iter = iter([
        "n", # Would you like to generate an indxr wiki? (n)
        "Ans 1", "Ans 2", # DDD Grill Questions
        "Extra info", # DDD Extra knowledge
        "1", # Platform selection (1 = Gemini)
        "", # Press ENTER after saving ONBOARDING_DOMAIN.md
        "y", # Are you sure you want to proceed?
    ])
    
    def mock_input_side_effect(prompt):
        try:
            return next(responses_iter)
        except StopIteration:
            return ""
            
    mock_input.side_effect = mock_input_side_effect

    # Mock subprocess.run for git clone
    def mock_run_side_effect(args, **kwargs):
        if "git" in args and "clone" in args:
            temp_dir = args[-1]
            bp_dir = Path(temp_dir) / "boilerplate-agent"
            bp_dir.mkdir(parents=True, exist_ok=True)
            (bp_dir / "AGENTS.md").write_text("# Agents\n@agents/feature-fetcher.md")
            (bp_dir / "orchestrator.md").write_text("# Orchestrator\n{{SUBAGENT_SYNTAX}}planner")
            (bp_dir / "rules").mkdir(parents=True, exist_ok=True)
            (bp_dir / "rules" / "dispatch_rules.md").write_text("# Rules\n**Negative Routing Rules")
            (bp_dir / "agents").mkdir(parents=True, exist_ok=True)
            (bp_dir / "agents" / "feature-fetcher.md").write_text("system_prompt: 'FF Prompt'")
            return MagicMock(returncode=0)
        return MagicMock(returncode=0)
    
    mock_subprocess_run.side_effect = mock_run_side_effect

    # Setup a dummy wiki in the project path
    setup_dummy_wiki(project_path)

    # 2. Run the CLI
    with patch('sys.argv', ['harness-wf', 'init', '--project-path', project_path, '--llm', 'gemini']):
        main()

    # 3. Assertions
    harness_dir = Path(project_path) / ".gemini"
    assert harness_dir.exists()
    
    # Verify Agents
    assert (harness_dir / "agents" / "agent1.md").exists()
    assert (harness_dir / "agents" / "agent2.md").exists()
    assert (harness_dir / "agents" / "my-custom-agent.md").exists()
    
    # Verify DDD
    assert (harness_dir / "ddd_context.json").exists()
    ddd_ctx = json.loads((harness_dir / "ddd_context.json").read_text())
    assert ddd_ctx["translation_map"]["Question 1?"] == "Ans 1"
    
    # Verify Platform Pointer
    assert (Path(project_path) / "GEMINI.md").exists()
    assert "# Agentic Harness" in (Path(project_path) / "GEMINI.md").read_text()
    
    # Verify Setup Script
    setup_script = harness_dir / "scripts" / "setup_harness.sh"
    assert setup_script.exists()
    assert "gemini extensions install" in setup_script.read_text()
    
    # Verify MCP Config
    mcp_json = harness_dir / "mcp.json"
    assert mcp_json.exists()
    mcp_data = json.loads(mcp_json.read_text())
    assert "indxr" in mcp_data["mcpServers"]
    assert "postgres" in mcp_data["mcpServers"]
    
    # Verify SME synthesis
    sme_agents = list((harness_dir / "agents").glob("*-sme.md"))
    assert len(sme_agents) >= 1
    sme_file = sme_agents[0]
    assert "# Role: Domain Subject Matter Expert" in sme_file.read_text()
    
    # Verify Orchestrator Rule Patching
    rules_path = harness_dir / "rules" / "dispatch_rules.md"
    assert "Domain SME Gateway" in rules_path.read_text()

    print("\nE2E Integration Test Verified Content and Structure Successfully!")
