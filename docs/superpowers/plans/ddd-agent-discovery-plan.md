# DDD Agent Discovery Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the DDD Alignment Grill answers into the agent discovery process so specialized agents are minted with user-validated domain knowledge intrinsically woven into their system prompts.

**Architecture:** 
The CLI workflow in `harness/cli.py` will be reordered to run the DDD grill before discovering agents. The `discovery_engine.py` will be updated to accept the resulting DDD context and inject it into the LLM prompt during agent discovery, instructing the LLM to specialize the generated system prompts based on the ubiquitous language and translation map.

**Tech Stack:** Python, Harness CLI

---

### Task 1: Update `discover_agents` signature and prompt

**Files:**
- Modify: `harness/discovery_engine.py`

- [ ] **Step 1: Update function signature and logic**

Update the `discover_agents` function to accept `ddd_context` and inject it into the `full_prompt`.

```python
def discover_agents(context_str: str, feature_fetcher_yaml_path: str, llm_provider: str, api_key: str, model: str = None, ddd_context: dict = None) -> list[dict]:
    # ... existing code ...
    
    print("Fetching remote skills for Agent Discovery...")
    arch_skill = fetch_remote_skill("https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/improve-codebase-architecture/SKILL.md")
    grill_docs_skill = fetch_remote_skill("https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/grill-with-docs/SKILL.md")

    ddd_prompt_section = ""
    if ddd_context:
        import json
        ddd_prompt_section = (
            "=== DOMAIN-DRIVEN DESIGN (DDD) CONTEXT ===\n"
            "The following domain knowledge and user alignment answers MUST be intrinsically woven into each agent's identity and responsibilities:\n"
            f"Ubiquitous Language: {ddd_context.get('ubiquitous_language', 'None provided')}\\n"
            f"Translation Map (User Answers): {json.dumps(ddd_context.get('translation_map', {}))}\\n"
            f"Legacy Hints: {json.dumps(ddd_context.get('legacy_hints', {}))}\\n\\n"
            "Ensure the agents' system prompts incorporate this domain-specific knowledge intrinsically. Do not just append it; use it to specialize their roles.\\n\\n"
        )

    full_prompt = (
        f"{system_prompt}\\n\\n"
        "You must utilize the principles from the following skills to guide your agent recommendations:\\n\\n"
        "=== IMPROVE CODEBASE ARCHITECTURE ===\\n"
        f"{arch_skill}\\n\\n"
        "=== GRILL WITH DOCS ===\\n"
        f"{grill_docs_skill}\\n\\n"
        "PROJECT CONTEXT:\\n"
        f"{context_str}\\n\\n"
        f"{ddd_prompt_section}"
        "TASK:\\n"
        "Recommend 3-5 specialized agents. For EACH agent, you MUST provide:\\n"
        "1. 'name': Concise name.\\n"
        "2. 'role': Brief responsibility summary.\\n"
        "3. 'zone': (Domain/Data/Handler/Core).\\n"
        "4. 'system_prompt': A comprehensive, 300-500 word Markdown system prompt. This prompt MUST:\\n"
        "   - Define their specific expertise relative to the project files.\\n"
        "   - Enforce the use of 'CodeGraph' MCP tools and local skills.\\n"
        "   - Define their 'Goldfish' phase responsibilities.\\n\\n"
        "Return as JSON: {'agents': [{'name': '...', 'role': '...', 'zone': '...', 'system_prompt': '...'}]}"
    )
    # ... rest of function ...
```

### Task 2: Reorder workflow in CLI

**Files:**
- Modify: `harness/cli.py`

- [ ] **Step 1: Move Stage 2.5 (DDD Grill) before agent discovery**

Locate the `main()` function and reorder the logic.

```python
        print("Stage 2: Dynamic Context Acquisition")
        from harness.discovery_engine import discover_agents, discover_ddd_context, acquire_mcp_context
        
        # Acquire context once
        context_str = acquire_mcp_context(args.project_path)
        
        final_ddd_context = None
        if args.ddd:
            print("\\nStage 2.5: DDD Onboarding Context Extraction")
            ddd_context_raw = discover_ddd_context(context_str, args.llm, api_key, args.model)
            grill_answers = run_ddd_grill(ddd_context_raw)
            
            final_ddd_context = {
                "ubiquitous_language": ddd_context_raw.get("context_draft", ""),
                "translation_map": grill_answers,
                "legacy_hints": ddd_context_raw.get("legacy_hints", {})
            }

        print("\\nDiscovering specialized agents...")
        recommended_agents = discover_agents(context_str, feature_fetcher_yaml, args.llm, api_key, args.model, ddd_context=final_ddd_context)
        
        print(f"Found {len(recommended_agents)} recommendations.")
        selected_agents = []
        print("\\n=== Recommended Agents ===")
```

Make sure to remove the old Stage 2.5 code block further down in the file.

### Task 3: Update Tests

**Files:**
- Modify: `tests/test_discovery_engine.py`

- [ ] **Step 1: Add test for ddd_context inclusion**

Add a new test case to ensure `discover_agents` handles the `ddd_context` parameter correctly without crashing.

```python
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
```

- [ ] **Step 2: Run tests to verify**
Run: `pytest tests/test_discovery_engine.py -v`
Expected: PASS
