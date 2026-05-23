import json
import subprocess
import time
import urllib.request
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from harness.renderer import TemplateRenderer

def acquire_mcp_context(project_path: str) -> str:
    """Acquires project context using CodeGraph and domain documentation."""
    
    context_parts = []
    
    # Priority 1: CONTEXT.md (The Wizard's output)
    context_file = os.path.join(project_path, "docs", "domain", "CONTEXT.md")
    if os.path.exists(context_file):
        with open(context_file, "r") as f:
            context_parts.append("=== PROJECT CORE CONTEXT ===\n" + f.read())

    # Priority 2: CodeGraph Symbols (Optional: If we want to seed with some high-level info)
    # For now, we rely on the agents using the MCP tool themselves, but we can check if DB exists
    codegraph_db = os.path.join(project_path, ".codegraph", "codegraph.db")
    if os.path.exists(codegraph_db):
        context_parts.append("\nCodeGraph index is available. Use `mcp_codegraph_codegraph_node` to map the architecture.")

    if context_parts:
        return "\n\n".join(context_parts)

    return None


def fetch_remote_skill(skill_url: str) -> str:
    """Fetches a skill definition from a raw GitHub URL."""
    try:
        req = urllib.request.Request(skill_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"WARNING: Failed to fetch skill from {skill_url}")
        print(f"Details: {e}")
        return None # Graceful fallback

def fetch_skill(skill_name: str, remote_url: str) -> str:
    """Fetches a skill definition from remote URL or fallback to local storage."""
    content = fetch_remote_skill(remote_url)
    if content:
        return content
        
    print(f"Attempting to load skill {skill_name} from local fallback...")
    home = os.path.expanduser("~")
    local_paths = [
        os.path.join(home, ".agents", "skills", skill_name, "SKILL.md"),
        os.path.join(home, ".gemini", "extensions", "superpowers", "skills", skill_name, "SKILL.md"),
        os.path.join(".agents", "skills", skill_name, "SKILL.md")
    ]
    
    for p in local_paths:
        if os.path.exists(p):
            try:
                with open(p, 'r') as f:
                    return f.read()
            except Exception:
                continue

    return None

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=20),
    retry=retry_if_exception_type(RuntimeError),
    before_sleep=lambda retry_state: print(f"Retrying LLM call (attempt {retry_state.attempt_number})..."),
    reraise=True
)
def query_llm(prompt: str, llm_provider: str, api_key: str, model: str = None) -> str:
    """Dispatches to the real LLM providers."""
    if llm_provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        use_model = model or "gpt-4o"
        response = client.chat.completions.create(
            model=use_model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
        
    elif llm_provider == "anthropic":
        import urllib.request
        import json
        use_model = model or "claude-3-5-sonnet-20241022"
        data = {
            "model": use_model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(data).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
        )
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["content"][0]["text"]
            
    elif llm_provider == "gemini":
        from google import genai
        client = genai.Client(api_key=api_key)
        # Use a reliable default model
        use_model = model or "gemini-2.5-flash-lite"
        
        try:
            # We are using generate_content, which is synchronous. It might take 10-20 seconds.
            response = client.models.generate_content(
                model=use_model,
                contents=prompt
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Gemini API call failed: {e}")
        
    raise ValueError(f"Unsupported LLM provider: {llm_provider}")

def discover_agents(context_str: str, feature_fetcher_yaml_path: str, llm_provider: str, api_key: str, model: str = None, ddd_context: dict = None) -> list[dict]:
    """Loads the system prompt and queries the LLM."""
    system_prompt = "You are the Feature Fetcher."
    try:
        import yaml
        with open(feature_fetcher_yaml_path, 'r') as f:
            config = next(yaml.safe_load_all(f), {})
            if config and isinstance(config, dict) and "system_prompt" in config:
                system_prompt = config["system_prompt"]
    except Exception as e:
        print(f"Warning: Could not load feature-fetcher prompt: {e}")

    print("Loading skills for Agent Discovery...")
    # Local skills are assumed to be present in the workspace
    arch_skill = "Improve Codebase Architecture: Analyze coupling and module boundaries."
    grill_docs_skill = "Grill With Docs: Ensure code changes strictly follow CONTEXT.md invariants."
    agentic_eval_skill = "Agentic Eval: Develop pipelines to test AI output."
    prompt_engineer_skill = "Prompt Engineer: Refactor agent prompts for determinism."

    ddd_prompt_section = ""
    if ddd_context:
        ddd_prompt_section = (
            "=== DOMAIN-DRIVEN DESIGN (DDD) CONTEXT ===\n"
            "The following domain knowledge and user alignment answers MUST be intrinsically woven into each agent's identity and responsibilities:\n"
            f"Ubiquitous Language: {ddd_context.get('ubiquitous_language', 'None provided')}\n"
            f"Translation Map (User Answers): {json.dumps(ddd_context.get('translation_map', {}))}\n"
            f"Legacy Hints: {json.dumps(ddd_context.get('legacy_hints', {}))}\n"
            f"Additional Knowledge: {ddd_context.get('additional_domain_knowledge', 'None provided')}\n\n"
            "Ensure the agents' system prompts incorporate this domain-specific knowledge intrinsically. Do not just append it; use it to specialize their roles.\n"
            "Specifically, you MUST use the Translation Map to bridge legacy terms with the Ubiquitous Language, and define their responsibilities based on the boundaries identified in these DDD concepts.\n\n"
        )

    full_prompt = (
        f"{system_prompt}\n\n"
        "You must utilize the principles from the following skills to guide your agent recommendations:\n\n"
        "=== IMPROVE CODEBASE ARCHITECTURE ===\n"
        f"{arch_skill}\n\n"
        "=== GRILL WITH DOCS ===\n"
        f"{grill_docs_skill}\n\n"
        "PROJECT CONTEXT:\n"
        f"{context_str}\n\n"
        f"{ddd_prompt_section}"
        "TASK:\n"
        "Recommend 3-5 specialized agents. For EACH agent, you MUST provide:\n"
        "1. 'name': Concise name.\n"
        "2. 'role': Brief responsibility summary.\n"
        "3. 'zone': (Domain/Data/Handler/Core).\n"
        "4. 'system_prompt': A comprehensive, 300-500 word Markdown system prompt. This prompt MUST:\n"
        "   - Define their specific expertise relative to the project files.\n"
        "   - Enforce a 'Graph-First' strategy. Before deep exploration, agents MUST use `mcp_codegraph_codegraph_search` and `mcp_codegraph_codegraph_node`.\n"
        "   - Enforce the use of 'codegraph' MCP tools (search, explore, context, callers) and local skills.\n"
        "   - Define their 'Goldfish' phase responsibilities.\n\n"
        "Return as JSON: {'agents': [{'name': '...', 'role': '...', 'zone': '...', 'system_prompt': '...'}]}"
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
        "2. Enforce the use of 'codegraph' MCP tools and local skills.\n"
        "3. Enforce a 'Graph-First' strategy using `mcp_codegraph_codegraph_search` and `mcp_codegraph_codegraph_node`.\n"
        "4. Define their role in the Goldfish Protocol (Phase 3) and Implementation (Phase 4).\n"
        "4. Incorporate the DDD context and ubiquitous language intrinsically.\n\n"
        "Return as JSON: {'name': '...', 'role': '...', 'zone': '...', 'system_prompt': '...'}"
    )
    
    print(f"Generating specialized prompt for custom agent: {name}...")
    response_text = query_llm(prompt, llm_provider, api_key, model)
    
    try:
        cleaned = response_text.replace("```json", "").replace("```", "").strip()
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}") + 1
        if start_idx != -1 and end_idx != 0:
            cleaned = cleaned[start_idx:end_idx]
            
        data = json.loads(cleaned)
        return data
    except Exception as e:
        print(f"Error generating custom agent: {e}")
        return {"name": name, "role": specs, "zone": "Core", "system_prompt": f"# {name}\n\n{specs}"}

def detect_tech_stack(project_path: str) -> str:
    """Heuristic detection of tech stack from project files, searching up to 2 levels deep."""
    stacks = set()
    
    # Files we are looking for
    markers = {
        "package.json": "Node.js/JavaScript",
        "tsconfig.json": "Node.js/TypeScript",
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "Pipfile": "Python",
        "setup.py": "Python",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "pom.xml": "JVM (Java/Kotlin)",
        "build.gradle": "JVM (Java/Kotlin)",
        "composer.json": "PHP"
    }

    # Walk directory structure, max 2 levels deep
    start_depth = project_path.rstrip(os.path.sep).count(os.path.sep)
    for root, dirs, files in os.walk(project_path):
        current_depth = root.count(os.path.sep)
        if current_depth - start_depth >= 2:
            dirs[:] = [] # Stop recursion
            continue
            
        for file in files:
            if file in markers:
                stacks.add(markers[file])

    # If TypeScript is found, prefer it over plain JavaScript
    if "Node.js/TypeScript" in stacks and "Node.js/JavaScript" in stacks:
        stacks.remove("Node.js/JavaScript")

    # Add Frontend marker for Node projects
    final_stacks = list(stacks)
    if any("Node.js" in s for s in final_stacks):
        final_stacks.append("Frontend")
        
    return ", ".join(sorted(final_stacks)) if final_stacks else "Unknown Stack"

def generate_onboarding_domain_doc(project_path: str, domain_summary: str, query_llm_fn=None, llm_provider=None, api_key=None, context_str="", boilerplate_dir: str = None):
    """Generates the ONBOARDING_DOMAIN.md template using LLM profiling and verified tools."""
    doc_path = os.path.join(project_path, "ONBOARDING_DOMAIN.md")
    
    # 1. Detect Tech Stack
    tech_stack = detect_tech_stack(project_path)
    
    # 2. Load and Flatten Tools Registry
    tools_registry = {}
    flattened_tools = []
    if boilerplate_dir:
        registry_path = os.path.join(boilerplate_dir, "onboarding", "tools.json")
        if os.path.exists(registry_path):
            try:
                with open(registry_path, "r") as f:
                    tools_registry = json.load(f)
                    # Flatten for LLM consumption
                    for cat, tools in tools_registry.get("categories", {}).items():
                        for t in tools:
                            t["category"] = cat
                            flattened_tools.append(t)
            except Exception as e:
                print(f"Warning: Could not load tools registry: {e}")

    # 3. Profile SME via LLM
    sme_name = "domain-sme"
    core_domain_value = "[USER INPUT REQUIRED]"
    invariants = "1. [USER INPUT REQUIRED: Add your own unbreakable rule here]\n"
    glossary = "*   **[Term 1]**: [USER INPUT REQUIRED: Define this term]\n"
    domain_events = "*   **[USER INPUT REQUIRED]**"
    context_mapping = "[USER INPUT REQUIRED]: e.g., 'We are a Conformist to the Legacy API.'"
    
    def is_forced(tool: dict, stack: str) -> bool:
        keywords = tool.get("force_if_keywords", [])
        return any(kw.lower() in stack.lower() for kw in keywords)

    # Pre-populate with forced tools based on tech stack
    forced_tools = [t for t in flattened_tools if is_forced(t, tech_stack)]
    recommended_mcps = [t for t in forced_tools if t.get("type") == "mcp"]
    recommended_skills = [t for t in forced_tools if t.get("type") != "mcp"]

    if query_llm_fn and llm_provider and api_key:
        prompt = f"""
        You are a Senior Architect. Analyze the project context and recommend a 'Domain SME' agent.
        
        Detected Tech Stack:
        {tech_stack}
        
        Project Context:
        {context_str[:5000]}
        
        Verified Tool Inventory:
        {json.dumps(flattened_tools)}
        
        Task:
        1. Name the SME (e.g. 'marketing-guardian').
        2. Define the Core Domain Value (what is the competitive advantage?).
        3. List 4 strict Domain Invariants (rules to protect logic).
        4. Define 4 Ubiquitous Language terms.
        5. List 2 key Domain Events (what happens that others need to know about?).
        6. Define the Context Mapping (how does this system relate to others?).
        7. Select 2-3 most relevant skills from the Inventory based on the Detected Tech Stack.
        8. Select 1-2 most relevant MCPs from the Inventory based on the Detected Tech Stack.
        
        Return ONLY valid JSON:
        {{
            "sme_name": "...",
            "core_domain_value": "...",
            "invariants": ["...", "..."],
            "glossary": {{"term": "definition"}},
            "domain_events": ["...", "..."],
            "context_mapping": "...",
            "skills": [{{"name": "...", "url": "..."}}],
            "mcps": [{{"name": "...", "command": "...", "type": "mcp"}}]
        }}
        """
        try:
            res = query_llm_fn(prompt, llm_provider, api_key)
            cleaned = res.replace("```json", "").replace("```", "").strip()
            start_idx = cleaned.find("{")
            end_idx = cleaned.rfind("}") + 1
            if start_idx != -1 and end_idx != 0:
                cleaned = cleaned[start_idx:end_idx]
            data = json.loads(cleaned)
            
            if data.get("sme_name"): sme_name = data["sme_name"]
            core_domain_value = data.get("core_domain_value", "[USER INPUT REQUIRED]")
            if data.get("invariants"):
                invariants = "\n".join([f"{i+1}. {inv}" for i, inv in enumerate(data["invariants"])])
            if data.get("glossary"):
                glossary = "\n".join([f"*   **{k}**: {v}" for k, v in data["glossary"].items()])
            
            domain_events = "*   **[USER INPUT REQUIRED]**"
            if data.get("domain_events"):
                domain_events = "\n".join([f"*   **{e}**" for e in data["domain_events"]])
            
            if data.get("context_mapping"):
                context_mapping = data["context_mapping"]
                
            if data.get("skills"): 
                for skill in data["skills"]:
                    if not any(s["name"] == skill["name"] for s in recommended_skills):
                        recommended_skills.append(skill)
            if data.get("mcps"): 
                for mcp in data["mcps"]:
                    if not any(m["name"] == mcp["name"] for m in recommended_mcps):
                        recommended_mcps.append(mcp)
        except Exception as e:
            print(f"\n[HARNESS] ⚠️ SME Profiling failed after retries: {e}")
            print("[HARNESS] Falling back to manual placeholders in ONBOARDING_DOMAIN.md")
            core_domain_value = "[USER INPUT REQUIRED: Define Core Domain Value]"
            domain_events = "*   **[USER INPUT REQUIRED: Define Domain Events]**"
            invariants = "1. [USER INPUT REQUIRED: Define Domain Invariants]"
            glossary = "*   **[USER INPUT REQUIRED: Define Glossary Terms]**"
            context_mapping = "[USER INPUT REQUIRED: Define Context Mapping]"

    # 4. Format Tools for Markdown
    skills_md = "- [ ] No skills recommended"
    if recommended_skills:
        # Format as: - [x] Name (URL)
        skills_md = "\n".join([f"- [x] {s.get('name', 'Unknown')} ({s.get('url', '')}) <!-- type:{s.get('type', 'skill')} -->" for s in recommended_skills])
        
    mcps_md = "- [ ] No MCPs recommended"
    if recommended_mcps:
        # Format as: - [x] Name (Command)
        mcps_md = "\n".join([f"- [x] {m.get('name', 'Unknown')} ({m.get('command', '')})" for m in recommended_mcps])

    # 5. Populate Template
    template_str = ""
    if boilerplate_dir:
        template_path = os.path.join(boilerplate_dir, "onboarding", "ONBOARDING_DOMAIN.md.template")
        if os.path.exists(template_path):
            with open(template_path, "r") as f:
                 template_str = f.read()
    
    # Fallback if template missing
    if not template_str:
         template_str = """# Project Onboarding Domain

**Detected Tech Stack:** <!--$ TECH_STACK $-->

Based on the codebase scan, I have identified **<!--$ DOMAIN_SUMMARY $-->** as a core complex domain. I propose creating a dedicated agent to protect this logic.

## Proposed Domain SME Agent

**Proposed Agent Name:** `@<!--$ SME_NAME $-->`
*(Edit the name above if incorrect. Must be lowercase.)*

## Deterministic DDD Alignment

### 1. Ubiquitous Language (Glossary)
*Key terms defined by business experts:*
<!--$ GLOSSARY $-->

### 2. Core Domain (Value Proposition)
*The single core capability that provides primary value:*
*   **<!--$ CORE_DOMAIN_VALUE $-->**

### 3. Aggregates & Invariants (Transactional Boundaries)
*Data that must absolutely always be updated together:*
<!--$ INVARIANTS $-->

### 4. Domain Events & Coordination (Asynchrony)
*Significant actions that others need to know about:*
<!--$ DOMAIN_EVENTS $-->

### 5. Context Mapping (Contract Ownership)
*Who dictates the shape of external data contracts:*
*   **<!--$ CONTEXT_MAPPING $-->**

## Proposed Skills
*(Delete the line of any skill you do NOT want installed)*
<!--$ SKILLS_MD $-->

## Proposed MCP Tools
*(Delete the line of any MCP you do NOT want installed)*
<!--$ MCPS_MD $-->

*(When you have finished editing this file, return to the terminal and press ENTER to continue minting)*
"""

    renderer = TemplateRenderer()
    context = {
        "TECH_STACK": tech_stack,
        "DOMAIN_SUMMARY": domain_summary,
        "SME_NAME": str(sme_name).lower(),
        "CORE_DOMAIN_VALUE": core_domain_value,
        "INVARIANTS": invariants,
        "GLOSSARY": glossary,
        "DOMAIN_EVENTS": domain_events,
        "CONTEXT_MAPPING": context_mapping,
        "SKILLS_MD": skills_md,
        "MCPS_MD": mcps_md
    }
    
    final_content = renderer.render_string(template_str, context)

    with open(doc_path, "w") as f:
        f.write(final_content)
    print(f"\n[HARNESS] Generated ONBOARDING_DOMAIN.md at {doc_path}")

