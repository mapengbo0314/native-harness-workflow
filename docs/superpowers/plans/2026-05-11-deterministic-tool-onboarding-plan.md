# Deterministic Onboarding Tool Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically include Playwright Interactive skill and MCP in `ONBOARDING_DOMAIN.md` for frontend projects via a `force_if_keywords` field in `tools.json`.

**Architecture:** Enhance the tools registry with a `force_if_keywords` property and update the discovery engine to deterministically inject tools that match the detected tech stack.

**Tech Stack:** Python, JSON

---

### Task 1: Update Tools Registry

**Files:**
- Modify: `boilerplate-agent/onboarding/tools.json`

- [ ] **Step 1: Add Playwright Interactive skill and update MCP entry**
Update `tools.json` to include the `playwright-interactive` skill and add `force_if_keywords` to both Playwright entries.

```json
{
  "categories": {
    "frontend": [
      {
        "name": "nextjs",
        "url": "https://raw.githubusercontent.com/PatrickJS/awesome-cline-prompts/main/prompts/nextjs.md",
        "keywords": ["react", "nextjs", "next.js", "frontend"]
      },
      {
         "name": "playwright",
         "command": "npx -y @modelcontextprotocol/server-playwright",
         "type": "mcp",
         "force_if_keywords": ["frontend"],
         "keywords": ["react", "nextjs", "frontend", "vue", "svelte"]
      },
      {
         "name": "playwright-interactive",
         "url": "https://github.com/openai/skills/blob/main/skills/.curated/playwright-interactive/SKILL.md",
         "type": "skill",
         "force_if_keywords": ["frontend"],
         "keywords": ["react", "nextjs", "frontend", "vue", "svelte"]
      }
    ],
    ...
  }
}
```

- [ ] **Step 2: Commit**
```bash
git add boilerplate-agent/onboarding/tools.json
git commit -m "feat(discovery): add force_if_keywords to tools registry for playwright"
```

---

### Task 2: Implement Forced Injection in Discovery Engine

**Files:**
- Modify: `harness/discovery_engine.py`

- [ ] **Step 0: Update `detect_tech_stack` to include 'Frontend' marker**
Modify `detect_tech_stack` to append " (Frontend)" if Node.js markers are found, to make keyword matching easier.

```python
    # ... inside detect_tech_stack ...
    # If TypeScript is found, prefer it over plain JavaScript
    if "Node.js/TypeScript" in stacks and "Node.js/JavaScript" in stacks:
        stacks.remove("Node.js/JavaScript")
    
    # Add Frontend marker for Node projects
    final_stacks = list(stacks)
    if any("Node.js" in s for s in final_stacks):
        final_stacks.append("Frontend")
        
    return ", ".join(sorted(final_stacks)) if final_stacks else "Unknown Stack"
```

- [ ] **Step 1: Update `generate_onboarding_domain_doc` logic**
Modify the function to identify forced tools and pre-populate the recommendations.

```python
    # 3. Profile SME via LLM
    # ... (after tools_registry is loaded)
    
    # Pre-populate with forced tools based on tech stack
    for tool in flattened_tools:
        if "force_if_keywords" in tool:
            for kw in tool["force_if_keywords"]:
                if kw.lower() in tech_stack.lower():
                    if tool.get("type") == "mcp":
                        if not any(m["name"] == tool["name"] for m in recommended_mcps):
                            recommended_mcps.append(tool)
                    else:
                        if not any(s["name"] == tool["name"] for s in recommended_skills):
                            recommended_skills.append(tool)
                    break
```

- [ ] **Step 2: Commit**
```bash
git add harness/discovery_engine.py
git commit -m "feat(discovery): implement deterministic tool injection based on force_if_keywords"
```

---

### Task 3: Verification with Tests

**Files:**
- Modify: `tests/unit/test_discovery_engine.py`

- [ ] **Step 1: Write failing test for forced injection**
Add a test case where a project matches "frontend" and verify the Playwright tools are present even if the LLM doesn't recommend them.

- [ ] **Step 2: Run test and verify success**
Run: `pytest tests/unit/test_discovery_engine.py -v`

- [ ] **Step 3: Commit**
```bash
git add tests/unit/test_discovery_engine.py
git commit -m "test(discovery): add test for forced tool injection"
```
