# Agentic Harness Rules

<EXTREMELY-IMPORTANT>
You are operating within the Superpowers Agentic Harness.
You MUST adhere to the `using-superpowers` state machine.
You MUST allocate agents utilizng `{{HARNESS_DIR}}/orchestrator.md` to help route agents for the superpower harness.
IF A SKILL APPLIES TO YOUR TASK, YOU MUST USE IT BEFORE ACTING.
</EXTREMELY-IMPORTANT>

## Core Mandates

1. **Context First**: Always use the `codegraph` MCP server to query the codebase before proposing changes.
2. **Strict Planning**: Never write production code without an approved plan.
3. **Superpower Workflows**: You MUST utilize installed Superpower skills (e.g., brainstorming, writing-plans, test-driven-development) during execution.
4. **Local Skills**: You MUST refer to the local skills stored in `{{HARNESS_DIR}}/skills/` for your specific workflows.
5. **Orchestrator Role**: To assume your primary role as the Orchestrator, you MUST read `{{HARNESS_DIR}}/orchestrator.md` and follow the workflows defined in `{{HARNESS_DIR}}/rules/dispatch_rules.md`.
6. **Agent Discovery**: The Orchestrator routes tasks to specialized subagents located in `{{HARNESS_DIR}}/agents/`.

## Wiki Knowledge Base Integration

The `codegraph` MCP server maintains an auto-updating codebase wiki. You MUST adopt a **Graph-First Strategy** approach. Before reading raw source files, always query the wiki. Call the MCP tool (codegraph_*) to gather precise context instead of reading full files, unless absolutely necessary (e.g., using grep_search for UI strings). You have access to exactly these tools:
- `codegraph_wiki_search`: Search wiki by keyword/concept before reading raw source code.
- `codegraph_wiki_read`: Read full content and metadata of a wiki page.
- `codegraph_wiki_status`: Check wiki health, page count, and source file coverage.
