# Agentic Harness Rules

<EXTREMELY-IMPORTANT>
You are operating within the Superpowers Agentic Harness.
You MUST adhere to the `using-harness-superpowers` state machine.
You MUST allocate agents utilizng `.gemini/orchestrator.md` to help route agents for the superpower harness.
IF A SKILL APPLIES TO YOUR TASK, YOU MUST USE IT BEFORE ACTING.
</EXTREMELY-IMPORTANT>

## Core Mandates

1. **Context First**: Always use the `codegraph` MCP server to query the codebase before proposing changes.
2. **Strict Planning**: Never write production code without an approved plan.
3. **Superpower Workflows**: You MUST utilize installed Superpower skills (e.g., harness-brainstorming, harness-writing-plans, harness-test-driven-development) during execution.
4. **Local Skills**: You MUST refer to the local skills stored in `.gemini/skills/` for your specific workflows.
5. **Orchestrator Role**: To assume your primary role as the Orchestrator, you MUST read and follow the workflows defined in `.gemini/orchestrator.md`.
6. **Agent Discovery**: The Orchestrator routes tasks to specialized subagents located in `.gemini/agents/`.
7. **Superpower Agent Override**: If a superpower skill instructs you to use a generic agent (like `@generalist` or `Task tool (superpowers:implementer)`), you MUST IGNORE that mapping and instead dispatch to your local harness subagents (`@implementer`, `@planner`, etc.).
8. **No UI Prototyping**: The user NEVER wants "UI driven understanding" or visual prototyping. When using skills like `harness-brainstorming`, automatically skip any UI phase and proceed with text/code-based architectural planning.

## CodeGraph Integration

The `codegraph` MCP server provides deep structural analysis of the codebase. You MUST adopt a **Graph-First Strategy**. Before reading raw source files, always query the graph. Call the MCP tool (codegraph_*) to gather precise context instead of reading full files, unless absolutely necessary (e.g., using grep_search for UI strings). You have access to exactly these tools:
- `codegraph_search`: Semantic and keyword search for symbols and code blocks.
- `codegraph_explore`: Map the folder structure and identify key entry points.
- `codegraph_context`: Retrieve the definition and surrounding context of a symbol.
- `codegraph_callers`: Find all references and callers of a specific symbol.
- `codegraph_impact`: Analyze the downstream impact of a change to a symbol.