# Engineering Skills Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Enhance the Agent Discovery phase by incorporating `improve-codebase-architecture` and `grill-with-docs` into the LLM prompt. Additionally, "bundle" these skills (along with `diagnose`) into the generated agent configurations so they are actively used for debugging and architectural tasks.

**Architecture:** 
1. `discovery_engine.py` will fetch the new skills remotely and append them to the `discover_agents` prompt.
2. `minting_engine.py` will update the `config.yaml` template for specialized agents to explicitly mandate the use of `improve-codebase-architecture`, `grill-with-docs`, and `diagnose` (specifically for bug handling).

---

### Task 1: Enhance Agent Discovery Prompt with Remote Skills

**Files:**
- Modify: `harness/discovery_engine.py`

- [ ] **Step 1: Fetch and inject skills into `discover_agents`**

Modify the `discover_agents` function to fetch the remote skills and include them in the `full_prompt`.

```python
def discover_agents(context_str: str, feature_fetcher_yaml_path: str, llm_provider: str, api_key: str, model: str = None) -> list[dict]:
    """Loads the system prompt and queries the LLM."""
    system_prompt = "You are the Feature Fetcher."
    try:
        import yaml
        with open(feature_fetcher_yaml_path, 'r') as f:
            config = yaml.safe_load(f)
            if "system_prompt" in config:
                system_prompt = config["system_prompt"]
    except Exception as e:
        print(f"Warning: Could not load feature-fetcher prompt: {e}")

    print("Fetching remote skills for Agent Discovery...")
    arch_skill = fetch_remote_skill("https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/improve-codebase-architecture.md")
    grill_docs_skill = fetch_remote_skill("https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/grill-with-docs.md")

    full_prompt = (
        f"{system_prompt}\n\n"
        "You must utilize the principles from the following skills to guide your agent recommendations:\n\n"
        "=== IMPROVE CODEBASE ARCHITECTURE ===\n"
        f"{arch_skill}\n\n"
        "=== GRILL WITH DOCS ===\n"
        f"{grill_docs_skill}\n\n"
        "PROJECT CONTEXT:\n"
        f"{context_str}\n\n"
        "Based on the mandate and skills above, output the required JSON."
    )
    
    print(f"Querying {llm_provider} for specialized agents...")
    response_text = query_llm(full_prompt, llm_provider, api_key, model)
    
    try:
        cleaned = response_text.replace("```json", "").replace("```", "").strip()
        # Find JSON boundaries if LLM included conversational text
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}") + 1
        if start_idx != -1 and end_idx != 0:
            cleaned = cleaned[start_idx:end_idx]
            
        data = json.loads(cleaned)
        return data.get("agents", [])
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse LLM response as JSON: {e}\nResponse:\n{response_text}")
        return [{"name": "Architect", "role": "General architecture and design", "zone": "Core"}]
```

- [ ] **Step 2: Commit discovery changes**

```bash
git add harness/discovery_engine.py
git commit -m "feat(discovery): inject architecture and grilling skills into agent discovery prompt"
```

---

### Task 2: Bundle Skills into Minted Agents

**Files:**
- Modify: `harness/minting_engine.py`

- [ ] **Step 1: Update the `config.yaml` template**

Modify the `config_yaml_content` string inside `minting_engine.py` to explicitly require the new engineering skills.

```python
        # Inject config.yaml
        ddd_section = ""
        if ddd_context:
            ddd_section = f"""  - prompt_section:
      title: Domain-Driven Design (DDD) Context
      content: |
        This project uses Domain-Driven Design principles.
        You MUST refer to the following DDD documentation in the `.gemini/ddd/` directory:
        - `context.md`: Defines the core domain terms and their meanings.
        - `translation_map.json`: Maps domain concepts to implementation details.
        
        Ensure your implementation aligns with these definitions.
    insert_after_sections: 'Role: {agent["name"]}'"""

        config_yaml_content = f"""coding_agent: true
agentic_mode: true
prompt_section_customization:
  add_prompt_sections:
  - prompt_section:
      title: Core Mandates
      content: |
        You are a specialized subagent operating within this repository's agent ecosystem.
        You have been delegated a specific task by the Orchestrator.
        1. Security & System Integrity: Protect secrets.
        2. Context Efficiency: Be strategic in tool usage.
        3. Superpower Workflows: You MUST utilize installed Superpower skills.
    insert_before_sections: artifacts
  - prompt_section:
      title: Indexer MCP Integration
      content: |
        You have access to the codebase index via the `CodeGraph` MCP server.
        - Strategic Fetching: Use `find`, `summarize`, `get_file_summary` via MCP.
    insert_after_sections: Core Mandates
  - prompt_section:
      title: 'Role: {agent["name"]}'
      content: |
        You are {agent["name"]}.
        Zone: {agent["zone"]}
        Responsibilities: {agent["role"]}
        
        SUPERPOWER MANDATE: You MUST invoke relevant superpower skills before finalizing work.
        - **Architecture:** Use `improve-codebase-architecture` when designing new features or proposing structural changes.
        - **Alignment:** Use `grill-with-docs` to align implementation details with the ubiquitous language.
        - **Debugging:** You MUST use the `diagnose` skill whenever a bug, stack trace, or unexpected behavior is reported by the user or encountered during testing.
    insert_after_sections: Indexer MCP Integration
{ddd_section}
"""
```

- [ ] **Step 2: Commit minting engine changes**

```bash
git add harness/minting_engine.py
git commit -m "feat(minting): bundle engineering skills (diagnose, architecture) into specialized agent configs"
```