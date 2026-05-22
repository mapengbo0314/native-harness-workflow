# Enhanced DDD Agent Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the DDD alignment and agent discovery process with additional domain knowledge capture and custom agent creation capabilities.

**Architecture:** 
1. Update `harness/cli.py` to capture extra domain knowledge in the DDD grill.
2. Add an interactive loop in `harness/cli.py` to allow users to specify custom agents.
3. Update `harness/discovery_engine.py` with `discover_custom_agent` to generate system prompts for user-defined agents using the accumulated context.

**Tech Stack:** Python, Harness CLI, LLM API

---

### Task 1: Enhance DDD Alignment Grill

**Files:**
- Modify: `harness/cli.py`

- [ ] **Step 1: Update `run_ddd_grill` to ask for additional domain knowledge**

```python
def run_ddd_grill(ddd_context: dict) -> dict:
    """Interactively grill the user with alignment questions."""
    print("\n=== DDD Alignment Grill ===")
    questions = ddd_context.get("questions", [])
    answers = {}
    
    if not questions:
        print("No alignment questions generated.")
    else:
        for i, q in enumerate(questions):
            print(f"\n[{i+1}/{len(questions)}] {q}")
            ans = input("> ").strip()
            answers[q] = ans
            
    # Enhancement: Extra question for general domain knowledge
    print("\n[Extra] Are there any other domain specific knowledge you would like to pass in?")
    extra_knowledge = input("> ").strip()
    if extra_knowledge:
        answers["__additional_domain_knowledge__"] = extra_knowledge
        
    return answers
```

- [ ] **Step 2: Update `main` to store the extra knowledge**

```python
        if args.ddd:
            print("\nStage 2.5: DDD Onboarding Context Extraction")
            ddd_context_raw = discover_ddd_context(context_str, args.llm, api_key, args.model)
            grill_answers = run_ddd_grill(ddd_context_raw)
            
            final_ddd_context = {
                "ubiquitous_language": ddd_context_raw.get("context_draft", ""),
                "translation_map": grill_answers,
                "legacy_hints": ddd_context_raw.get("legacy_hints", {}),
                "additional_domain_knowledge": grill_answers.get("__additional_domain_knowledge__", "")
            }
```

- [ ] **Step 3: Commit**
```bash
git add harness/cli.py
git commit -m "feat: enhance DDD grill with additional domain knowledge capture"
```

### Task 2: Implement Custom Agent Discovery

**Files:**
- Modify: `harness/discovery_engine.py`

- [ ] **Step 1: Add `discover_custom_agent` function**

```python
def discover_custom_agent(name: str, specs: str, context_str: str, ddd_context: dict, llm_provider: str, api_key: str, model: str = None) -> dict:
    """Generates a system prompt for a custom user-defined agent."""
    
    ddd_prompt_section = ""
    if ddd_context:
        ddd_prompt_section = (
            "=== DOMAIN-DRIVEN DESIGN (DDD) CONTEXT ===\n"
            f"Ubiquitous Language: {ddd_context.get('ubiquitous_language', 'None provided')}\n"
            f"Translation Map: {json.dumps(ddd_context.get('translation_map', {}))}\n"
            f"Additional Knowledge: {ddd_context.get('additional_domain_knowledge', 'None provided')}\n\n"
        )

    prompt = (
        "You are an Agent Architect. Your task is to generate a high-quality system prompt for a new specialized agent.\n\n"
        "=== PROJECT CONTEXT ===\n"
        f"{context_str}\n\n"
        f"{ddd_prompt_section}"
        "=== USER REQUEST ===\n"
        f"Agent Name: {name}\n"
        f"Agent Role/Specs: {specs}\n\n"
        "=== TASK ===\n"
        "Generate a comprehensive, 300-500 word Markdown system prompt for this agent. The prompt MUST:\n"
        "1. Define their specific expertise relative to the project files.\n"
        "2. Enforce the use of 'CodeGraph' MCP tools and local skills.\n"
        "3. Define their role in the Goldfish Protocol (Phase 3) and Implementation (Phase 4).\n"
        "4. Incorporate the DDD context and ubiquitous language intrinsically.\n\n"
        "Return as JSON: {'name': '...', 'role': '...', 'zone': '...', 'system_prompt': '...'}"
    )
    
    response_text = query_llm(prompt, llm_provider, api_key, model)
    
    try:
        cleaned = response_text.replace("```json", "").replace("```", "").strip()
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}") + 1
        if start_idx != -1 and end_idx != 0:
            cleaned = cleaned[start_idx:end_idx]
            
        return json.loads(cleaned)
    except Exception as e:
        print(f"Error generating custom agent: {e}")
        return {"name": name, "role": specs, "zone": "Core", "system_prompt": f"# {name}\n\n{specs}"}
```

- [ ] **Step 2: Commit**
```bash
git add harness/discovery_engine.py
git commit -m "feat: add discover_custom_agent to discovery_engine"
```

### Task 3: Add Custom Agent Creation Loop to CLI

**Files:**
- Modify: `harness/cli.py`

- [ ] **Step 1: Update `main` to include custom agent creation loop**

```python
        # ... after selected_agents loop ...
        while True:
            choice = input("\nWould you like to create an additional custom agent? (y/N): ").strip().lower()
            if choice not in ['y', 'yes']:
                break
                
            custom_name = input("Enter Agent Name: ").strip()
            if not custom_name: continue
            custom_specs = input("Enter Agent Specs/Role: ").strip()
            if not custom_specs: continue
            
            print(f"Generating specialized prompt for {custom_name}...")
            from harness.discovery_engine import discover_custom_agent
            custom_agent = discover_custom_agent(custom_name, custom_specs, context_str, final_ddd_context, args.llm, api_key, args.model)
            selected_agents.append(custom_agent)
            print(f"Agent {custom_name} added.")
```

- [ ] **Step 2: Commit**
```bash
git add harness/cli.py
git commit -m "feat: add custom agent creation loop to CLI"
```

### Task 4: Verification

**Files:**
- Modify: `tests/unit/test_discovery_engine.py`

- [ ] **Step 1: Add test for `discover_custom_agent`**

```python
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
```

- [ ] **Step 2: Run tests**
Run: `pytest tests/unit/test_discovery_engine.py -v`
Expected: PASS

- [ ] **Step 3: Commit**
```bash
git add tests/unit/test_discovery_engine.py
git commit -m "test: add test for discover_custom_agent"
```
