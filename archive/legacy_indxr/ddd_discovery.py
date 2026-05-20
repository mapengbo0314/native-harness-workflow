import json

# Legacy discover_ddd_context function, archived during CodeGraph swap.

def discover_ddd_context(context_str: str, llm_provider: str, api_key: str, model: str = None) -> dict:
    """Extracts DDD context using remote skills and deterministic questions."""
    print("Loading skills for DDD alignment...")
    grill_me_skill = fetch_skill("grill-me", "https://raw.githubusercontent.com/mattpocock/skills/main/skills/productivity/grill-me/SKILL.md")
    grill_with_docs_skill = fetch_skill("grill-with-docs", "https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/grill-with-docs/SKILL.md")
    agentic_eval_skill = fetch_skill("agentic-eval", "https://raw.githubusercontent.com/github/awesome-copilot/main/skills/agentic-eval/SKILL.md")
    prompt_engineer_skill = fetch_skill("prompt-engineer", "https://raw.githubusercontent.com/Jeffallan/claude-skills/main/skills/prompt-engineer/SKILL.md")

    prompt = (
        "You are a strict Domain-Driven Design architect. Analyze the project context and execute the provided skills.\n\n"
        "AVOID TECHNICAL PEDANTRY: Do not ask about technical naming (e.g., 'spend vs cost') or implementation details (e.g., 'dataframe skeletons') unless they represent a fundamental business misunderstanding.\n\n"
        "=== DETERMINISTIC DDD FRAMEWORK ===\n"
        "Focus your analysis and questions on these 5 core areas:\n"
        "1. UBIQUITOUS LANGUAGE: What is the exact vocabulary business experts use? Are there overloaded terms across contexts?\n"
        "2. CORE DOMAIN: What is the single core capability that provides primary value/competitive advantage?\n"
        "3. AGGREGATES & INVARIANTS: What data MUST be updated together in a single transaction to maintain business rules?\n"
        "4. DOMAIN EVENTS: Who needs to know when a significant action is completed? (Eventual consistency needs)\n"
        "5. CONTEXT MAPPING: Who dictates the shape of the data contract when interacting with external/other systems?\n\n"
        "Apply the 'agentic-eval' and 'prompt-engineer' skills to self-critique your domain definitions.\n\n"
        "=== GRILL-WITH-DOCS SKILL ===\n"
        f"{grill_with_docs_skill}\n\n"
        "=== GRILL-ME SKILL ===\n"
        f"{grill_me_skill}\n\n"
        "Your task:\n"
        "1. Draft a context definition (context.md style) structured by the 5 Deterministic DDD areas.\n"
        "2. Identify genuine domain ambiguities that cannot be resolved by reading the code.\n"
        "3. Generate 3-5 sharp questions that force the user to define business boundaries, NOT implementation details.\n\n"
        "Your response MUST be in JSON format with exactly these keys:\n"
        "- 'context_draft': A string containing the drafted domain context.\n"
        "- 'questions': A list of strings representing alignment questions.\n"
        "- 'legacy_hints': A dictionary containing hints about legacy components.\n\n"
        f"PROJECT CONTEXT:\n{context_str}"
    )    
    response_text = query_llm(prompt, llm_provider, api_key, model)

    
    try:
        cleaned = response_text.replace("```json", "").replace("```", "").strip()
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}") + 1
        if start_idx != -1 and end_idx != 0:
            cleaned = cleaned[start_idx:end_idx]
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse DDD LLM response as JSON: {e}")
        return {"context_draft": "", "questions": [], "legacy_hints": {}}