from harness.discovery_engine import detect_tech_stack
import os
import json

def test_deep_discovery_playwright():
    # Mock LLM function
    def mock_query_llm(prompt, provider, api_key):
        return json.dumps({
            "unit": {"framework": "jest", "command": "npm test"},
            "e2e": {"framework": "playwright", "command": "npx playwright test"},
            "capabilities": ["Playwright", "TypeScript"]
        })

    # Use absolute path to be safe, although relative might work
    project_path = os.path.abspath("tests/fixtures/discovery_mock")
    # We expect detect_tech_stack to now return more than just "Node.js/JavaScript"
    # It should include evidence of Playwright.
    result = detect_tech_stack(project_path, query_llm_fn=mock_query_llm, llm_provider="mock", api_key="mock")
    
    # This is expected to succeed now
    assert isinstance(result, dict)
    assert "Playwright" in result["capabilities"]
    # Adjust assertion to match structured strategy
    assert result["strategy"]["e2e"]["command"] == "npx playwright test"
    assert "Node.js/JavaScript" in result["stacks"]
