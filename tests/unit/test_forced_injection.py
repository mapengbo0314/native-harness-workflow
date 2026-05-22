import os
import json
from unittest import mock
from harness.discovery_engine import generate_onboarding_domain_doc

@mock.patch('harness.discovery_engine.query_llm')
def test_generate_onboarding_domain_doc_forced_injection(mock_query_llm, tmp_path):
    project_path = str(tmp_path)
    
    # We create a dummy package.json to trigger Frontend stack detection
    with open(os.path.join(project_path, "package.json"), "w") as f:
        f.write('{"name": "test"}')
        
    boilerplate_dir = os.path.join(project_path, "boilerplate-agent")
    onboarding_dir = os.path.join(boilerplate_dir, "onboarding")
    os.makedirs(onboarding_dir)
    
    # Mock tool registry with a forced tool
    tools_registry = {
        "categories": {
            "frontend": [
                {
                    "name": "playwright",
                    "command": "npx playwright",
                    "type": "mcp",
                    "force_if_keywords": ["frontend"]
                },
                {
                    "name": "testing-skill",
                    "url": "http://test",
                    "type": "skill",
                    "force_if_keywords": ["frontend"]
                }
            ]
        }
    }
    with open(os.path.join(onboarding_dir, "tools.json"), "w") as f:
        json.dump(tools_registry, f)
        
    with open(os.path.join(onboarding_dir, "ONBOARDING_DOMAIN.md.template"), "w") as f:
        f.write("{{SKILLS_MD}}\n{{MCPS_MD}}")

    mock_query_llm.return_value = '{"skills": [], "mcps": []}'
    
    generate_onboarding_domain_doc(
        project_path, 
        "Test Domain", 
        query_llm_fn=mock_query_llm, 
        llm_provider="test", 
        api_key="test", 
        context_str="", 
        boilerplate_dir=boilerplate_dir
    )
    
    doc_path = os.path.join(project_path, "ONBOARDING_DOMAIN.md")
    assert os.path.exists(doc_path)
    
    with open(doc_path, 'r') as f:
        content = f.read()
        
    # The forced tools should be injected regardless of the LLM response
    assert "- [x] testing-skill (http://test)" in content
    assert "- [x] playwright (npx playwright)" in content

