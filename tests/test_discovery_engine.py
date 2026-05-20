import os
import tempfile
from harness.discovery_engine import acquire_mcp_context
import pytest
from unittest import mock
from harness.discovery_engine import discover_agents, discover_custom_agent, generate_onboarding_domain_doc

@mock.patch("harness.discovery_engine.fetch_remote_skill")
@mock.patch("harness.discovery_engine.query_llm")
def test_discover_agents(mock_query_llm, mock_fetch_skill):
    mock_fetch_skill.return_value = "Mocked skill"
    # Mock the LLM returning a valid JSON string
    mock_query_llm.return_value = '''
    {
      "agents": [
        {"name": "AuthAgent", "role": "Handles authentication logic", "zone": "Security"}
      ]
    }
    '''
    
    agents = discover_agents("Mocked context", "/fake/feature-fetcher.yaml", "gemini", "fake-key")
    assert len(agents) == 1
    assert agents[0]["name"] == "AuthAgent"
    mock_query_llm.assert_called_once()

@mock.patch("harness.discovery_engine.fetch_remote_skill")
@mock.patch("harness.discovery_engine.query_llm")
def test_discover_agents_with_ddd_context(mock_query_llm, mock_fetch_skill):
    mock_fetch_skill.return_value = "Mocked skill"
    mock_query_llm.return_value = '''
    {
      "agents": [
        {"name": "DomainExpert", "role": "Knows DDD", "zone": "Domain"}
      ]
    }
    '''
    
    ddd_ctx = {
        "ubiquitous_language": "Foo means Bar",
        "translation_map": {"Q": "A"},
        "legacy_hints": {}
    }
    
    agents = discover_agents("Mocked context", "/fake/feature-fetcher.yaml", "gemini", "fake-key", ddd_context=ddd_ctx)
    assert len(agents) == 1
    assert agents[0]["name"] == "DomainExpert"
    
    # Check if DDD context was injected in prompt
    call_args = mock_query_llm.call_args[0][0]
    assert "DOMAIN-DRIVEN DESIGN (DDD) CONTEXT" in call_args
    assert "Foo means Bar" in call_args

@mock.patch("harness.discovery_engine.query_llm")
def test_discover_custom_agent(mock_query_llm):
    mock_query_llm.return_value = '''
    {
      "name": "CustomAgent",
      "role": "Custom Role",
      "zone": "Core",
      "system_prompt": "Custom Prompt"
    }
    '''
    
    agent = discover_custom_agent("CustomAgent", "Custom Specs", "Context", {"ubiquitous_language": "foo"}, "gemini", "key")
    assert agent["name"] == "CustomAgent"
    assert "Custom Prompt" in agent["system_prompt"]

def test_acquire_mcp_context_with_bundle():
    with tempfile.TemporaryDirectory() as temp_dir:
        bundle_dir = os.path.join(temp_dir, "my_bundle")
        wiki_dir = os.path.join(bundle_dir, "wiki")
        os.makedirs(wiki_dir)
        with open(os.path.join(wiki_dir, "index.md"), "w") as f:
            f.write("Bundle Index")
        with open(os.path.join(wiki_dir, "architecture.md"), "w") as f:
            f.write("Bundle Arch")

        # project_path is dummy, it should prioritize bundle
        context = acquire_mcp_context("/dummy/path", bundle_path=bundle_dir)
        assert context is not None
        assert "Bundle Index" in context
        assert "Bundle Arch" in context

def test_acquire_mcp_context_no_wiki():
    context = acquire_mcp_context("/dummy/path", bundle_path=None)
    assert context is None

def test_acquire_mcp_context_bundle_indxr_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        bundle_dir = os.path.join(temp_dir, ".indxr")
        wiki_dir = os.path.join(bundle_dir, "wiki")
        os.makedirs(wiki_dir)
        with open(os.path.join(wiki_dir, "index.md"), "w") as f:
            f.write("Indxr Index")
            
        context = acquire_mcp_context("/dummy/path", bundle_path=bundle_dir)
        assert context is not None
        assert "Indxr Index" in context

def test_generate_onboarding_domain_doc(tmp_path):
    project_path = str(tmp_path)
    mock_llm_response = "Identified Domain: Financial Ledger"
    
    generate_onboarding_domain_doc(project_path, mock_llm_response)
    
    doc_path = os.path.join(project_path, "ONBOARDING_DOMAIN.md")
    assert os.path.exists(doc_path)
    
    with open(doc_path, 'r') as f:
        content = f.read()
        assert "Proposed Domain SME Agent" in content
        assert "Financial Ledger" in content
        assert "Invariants" in content
        assert "Ubiquitous Language" in content
@mock.patch('harness.discovery_engine.query_llm')
def test_generate_onboarding_domain_doc_with_tools(mock_query_llm, tmp_path):
    project_path = str(tmp_path)
    mock_llm_response = "Identified Domain: Financial Ledger"
    
    # Mock the tool scout response
    mock_query_llm.return_value = '{"skills": [{"name": "pytest", "url": "http://test"}], "mcps": [{"name": "sql", "command": "npx -y sql-mcp"}]}'
    
    # We need to pass the query_llm fn and keys to generate_onboarding_domain_doc now
    generate_onboarding_domain_doc(project_path, mock_llm_response, query_llm_fn=mock_query_llm, llm_provider="provider", api_key="key", context_str="some context")
    
    doc_path = os.path.join(project_path, "ONBOARDING_DOMAIN.md")
    assert os.path.exists(doc_path)
    
    with open(doc_path, 'r') as f:
        content = f.read()
        assert "## Proposed Skills" in content
        assert "- [x] pytest (http://test)" in content
        assert "## Proposed MCP Tools" in content
        assert "- [x] sql (npx -y sql-mcp)" in content

@mock.patch('harness.discovery_engine.query_llm')
def test_generate_onboarding_domain_doc_forced_injection(mock_query_llm, tmp_path):
    project_path = str(tmp_path)
    
    # Create a package.json to trigger 'Frontend' tech stack detection
    with open(os.path.join(project_path, "package.json"), "w") as f:
        f.write("{}")

    # Create a dummy boilerplate_dir with tools.json that forces playwright
    boilerplate_dir = os.path.join(project_path, "boilerplate")
    os.makedirs(os.path.join(boilerplate_dir, "onboarding"))
    with open(os.path.join(boilerplate_dir, "onboarding", "tools.json"), "w") as f:
        json_data = {
            "categories": {
                "testing": [
                    {
                        "name": "playwright",
                        "command": "npx -y @playwright/mcp-server",
                        "type": "mcp",
                        "force_if_keywords": ["frontend"]
                    }
                ]
            }
        }
        import json
        json.dump(json_data, f)
        
    mock_llm_response = "Identified Domain: Financial Ledger"
    
    # Mock the tool scout response to NOT include playwright
    mock_query_llm.return_value = '{"skills": [], "mcps": [{"name": "sql", "command": "npx -y sql-mcp", "type": "mcp"}]}'
    
    generate_onboarding_domain_doc(
        project_path, 
        mock_llm_response, 
        query_llm_fn=mock_query_llm, 
        llm_provider="provider", 
        api_key="key", 
        context_str="some context",
        boilerplate_dir=boilerplate_dir
    )
    
    doc_path = os.path.join(project_path, "ONBOARDING_DOMAIN.md")
    assert os.path.exists(doc_path)
    
    with open(doc_path, 'r') as f:
        content = f.read()
        assert "- [x] playwright" in content
        assert "- [x] sql" in content
