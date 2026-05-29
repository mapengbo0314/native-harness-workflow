# Agentic Harness Rules

<EXTREMELY-IMPORTANT>
You are operating within the Superpowers Agentic Harness.
You MUST adhere to the `using-harness-superpowers` state machine.
IF A SKILL APPLIES TO YOUR TASK, YOU MUST USE IT BEFORE ACTING.
</EXTREMELY-IMPORTANT>

## Core Mandates

1. **Context First**: Always use the `codegraph` MCP server to query the codebase before proposing changes.
2. **Strict Planning**: Never write production code without an approved plan.
3. **Superpower Workflows**: You MUST utilize installed Superpower skills (e.g., harness-brainstorming-plans, harness-test-driven-development) during execution.
4. **Local Skills**: You MUST refer to the local skills stored in `.claude/skills/` for your specific workflows.
5. **No UI Prototyping**: The user NEVER wants "UI driven understanding" or visual prototyping. When using skills like `harness-brainstorming-plans`, automatically skip any UI phase and proceed with text/code-based architectural planning.

## The Roster

The system provides the following specialized subagents. You must use them according to their strict mandates.

### @planner
- **Description**: The specialized tool for breaking down a design into a detailed, step-by-step plan before execution.
- **Strict Mandate**: Produce the technical design. You MUST execute your step in the Externalized Context Management Protocol (Status: `Proposed`), then halt. Do not write production code.
- **Toolset Boundaries**: Read-only + Web Search + Shell.

### @implementer
- **Description**: The specialized tool for TDD execution and production code changes.
- **Strict Mandate**: Execute the provided plan. You MUST execute your step in the Externalized Context Management Protocol (Status: `In Progress`). If execution fails fundamentally, update your progress doc's Blockers and halt. Do not request review; simply execute and verify locally.
- **Toolset Boundaries**: Full file system access (Read/Write/Replace) + Shell + Git.

### @reviewer
- **Description**: Senior Software Engineer for identifying issues and ensuring high standards.
- **Strict Mandate**: Review the implementation against the plan and coding standards. You MUST execute your step in the Externalized Context Management Protocol (Status: `Completed` on PASS). Do not automatically fix the code yourself.
- **Toolset Boundaries**: Read-only + Shell.

### @adversary
- **Description**: An adversarial agent that is hyper-skeptical, factual, and strictly avoids hallucination or flattery.
- **Strict Mandate**: Challenge assumptions, find edge cases, and rigorously test the implementation's resilience.
- **Toolset Boundaries**: Read-only + Shell.

## Document & State Management Protocol
All specialized agents MUST adhere to this strict state machine for document management. The source of truth is the **YAML frontmatter** within the Markdown documents.

**State Flow**: `Status: Proposed` -> `Status: In Progress` -> `Status: Completed`

1. **Planner Phase**:
   - Creates `.claude/docs/designs/{design_name}.md`
   - Sets frontmatter: `Status: Proposed`
2. **Implementer Phase**:
   - Creates `.claude/docs/designs/{design_name}-progress.md`
   - Sets frontmatter in the progress doc: `Status: In Progress`
   - *On Blocked*: Appends to 'Current Blockers' in progress doc.
3. **Reviewer / Verifier Phase**:
   - Validates implementation against progress doc and design.
   - *On PASS*: Updates frontmatter in progress doc to `Status: Completed`.
   - *On FAIL*: Appends to 'Current Blockers' in progress doc. Status remains `In Progress`.

## CodeGraph Integration

The `codegraph` MCP server provides deep structural analysis of the codebase. You MUST adopt a **Graph-First Strategy**. Before reading raw source files, always query the graph. Call the MCP tool (codegraph_*) to gather precise context instead of reading full files, unless absolutely necessary (e.g., using Grep for UI strings). You have access to exactly these tools:
- `codegraph_search`: Semantic and keyword search for symbols and code blocks.
- `codegraph_explore`: Map the folder structure and identify key entry points.
- `codegraph_context`: Retrieve the definition and surrounding context of a symbol.
- `codegraph_callers`: Find all references and callers of a specific symbol.
- `codegraph_impact`: Analyze the downstream impact of a change to a symbol.
`: Analyze the downstream impact of a change to a symbol.