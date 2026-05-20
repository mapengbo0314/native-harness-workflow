# CodeGraph MCP Full Swap Design

## Goal
Replace the legacy `indxr` (Semantic Wiki) and `ddd_context` (Domain-Driven Design) modules with `@colbymchenry/codegraph` as the exclusive context engine for the Agentic Harness. This shift prioritizes token efficiency, deterministic symbol resolution (AST-based), and impact analysis over LLM-generated summaries. 

## The Golden Rule for Agents
All agent system prompts must embed this core principle:
**"Call the MCP tool (`codegraph_*`) to gather precise context instead of reading the full files, unless you absolutely have to."**

## 1. Legacy Archival
To reduce bloat and prevent system confusion, the old NLP-based discovery tools will be isolated and removed from the active runtime:
- **Archive:** Create `archive/legacy_indxr/` and add `archive/` to `.gitignore`.
- **Relocation:** Move functions related to `discover_ddd_context` and heavy LLM wiki parsing from `harness/discovery_engine.py` into the archive.
- **Cleanup:** Remove `ddd_context` arguments and parsing logic from `harness/cli.py` and `harness/minting_engine.py`. Remove `ddd_context.json` generation entirely.

## 2. CLI & CodeGraph Onboarding
The entry point of the harness must guarantee that the CodeGraph database exists before agents are dispatched.
- **Detection:** In `harness/cli.py`, check for the existence of `.codegraph/codegraph.db` in the project root.
- **Auto-Initialization:** If the database does not exist, prompt the user and automatically execute the index builder: `npx -y @colbymchenry/codegraph init --index`.
- **MCP Configuration:** Modify `mint_workspace` in `harness/minting_engine.py`. Instead of registering `indxr`, it must inject the CodeGraph MCP server command (`npx -y @colbymchenry/codegraph serve --mcp`) into the platform's `mcp.json` file.

## 3. Orchestrator Rule Refactoring & Direct-Dispatch Matrix
To achieve maximum determinism, we are abolishing the separation between `orchestrator.md` and `dispatch_rules.md`. Forcing an LLM to read a secondary file to understand its state machine is an anti-pattern. We are merging them into a single, unified context window.
Furthermore, we are replacing the sequential "Phase 0 -> 1 -> 2" waterfall with a **Direct-Dispatch Decision Matrix**, instantly routing to the exact tool and subagent required based on intent.

### The Direct-Dispatch Branches
*   **Branch A: Bug Fix / Diagnosis**
    *   *Trigger:* User says "X is broken" or posts a stack trace.
    *   *Action:* Orchestrator uses `codegraph_search` and `codegraph_callers` to find the erroring function.
    *   *Dispatch:* Sends context directly to `@implementer` (with `systematic-debugging` skill). No planning required.
*   **Branch B: Feature Request & Architectural Planning**
    *   *Trigger:* User says "Build a new X" or "Implement Y."
    *   *Action:* Orchestrator uses `codegraph_explore` to map the folder structure.
    *   *Dispatch:* Sends context to `@planner` (with `brainstorming`, `writing-plans`, and `grill-with-docs` skills) to write the spec.
*   **Branch C: Codebase Questioning & Knowledge Retrieval**
    *   *Trigger:* User asks "How does X work?" or "Where is the auth logic?"
    *   *Action:* Orchestrator uses `codegraph_search` and `codegraph_context`.
    *   *Dispatch:* NONE. The Orchestrator answers directly. No files are modified.
*   **Branch D: Surgical Edit (Fast Path)**
    *   *Trigger:* User says "Change the color of the button" or "Fix this typo."
    *   *Action:* Orchestrator uses `codegraph_context` to grab the exact 5 lines of code.
    *   *Dispatch:* Sends context directly to `@implementer` (bypassing heavy workflows).

### Deterministic Routing Mechanism (The "Eval Block")
To mathematically guarantee that the LLM selects the correct branch and doesn't hallucinate a workflow, the Orchestrator's system prompt MUST enforce a mandatory evaluation step. 

Before using ANY tool or dispatching ANY subagent, the Orchestrator MUST output a structured evaluation block:

```json
{
  "intent_analysis": "The user is asking how the database connection works.",
  "selected_branch": "Branch C: Codebase Questioning",
  "required_tools": ["codegraph_search", "codegraph_context"],
  "dispatch_target": "None (Direct Answer)"
}
```
By forcing the LLM to output its logical deduction in JSON format *before* it generates tool-call syntax, we enforce a deterministic chain-of-thought that prevents hallucinated routing.

## 4. CLI Wizard & Context Injection (Platform Engineering Rollout)
To support a "White-Glove Onboarding" rollout model, we must guarantee that the rules established during the kickoff meeting are mathematically enforced by the subagents, particularly the `@implementer`.

### The CLI Context Wizard
We will replace the automated LLM DDD extraction with a lightning-fast terminal wizard in `harness/cli.py` during `init`:
- **Prompt 1:** "In 1-2 sentences, what is the core purpose of this project?"
- **Prompt 2:** "What are 2-3 specific vocabulary terms (Ubiquitous Language) used in this codebase?"
- **Prompt 3:** "Are there any strict architectural rules or invariants? (e.g., 'Never delete users, only deactivate')"
- **Output:** The CLI saves these inputs directly into `docs/domain/CONTEXT.md`.

### The "Ghost Injection" (Subagent Enforcement)
To prevent the developer from bypassing architectural rules on fast-path edits (Branch A or D):
- **Minting Engine Update:** When `harness/minting_engine.py` generates the `implementer.md` file for the workspace, it MUST read the "Strict Invariants" from the newly created `CONTEXT.md` and append them directly to the bottom of the `@implementer`'s system prompt.
- **Guarantee:** This ensures that even if the Orchestrator skips the planning phase, the execution agent is hard-coded with the project's non-negotiable rules.

## 5. Guaranteed Skill Onboarding (`grill-with-docs`)
To guarantee that `grill-with-docs` (and other critical discovery skills) are available to the harness regardless of the platform:
- **Registry Update:** In `boilerplate-agent/onboarding/tools.json` (or equivalent registry), explicitly mark `grill-with-docs` as a "forced" skill for all tech stacks.
- **Minting Engine:** Update `harness/minting_engine.py` to ensure that forced skills are automatically downloaded into the workspace's `.gemini/skills/` (or `.claude/skills/`) directory during initialization, bypassing any user opt-out prompts for core architectural skills.

## 4. Agent System Prompts Refactor & Architect Deprecation
Update the boilerplate agent templates in `boilerplate-agent/agents/*.md`.
- **Architect Deprecation:** Delete the `@architect` agent entirely (`boilerplate-agent/agents/architect.md`). With the introduction of deterministic CodeGraph tools (`codegraph_callers`, `codegraph_impact`), codebase navigation is no longer a multi-turn, complex investigation requiring a dedicated "reading" agent. The Architect's responsibilities are shifted: the **Orchestrator** handles high-level questioning, and the **Planner** handles deep dependency mapping during feature design.
- Strip all mentions of the "Wiki-First strategy" and `mcp_indxr_*` tools from remaining agents.
- Introduce the "Graph-First strategy."
- Explicitly list the available `codegraph_*` tools in the agent toolset constraints, paired with the Golden Rule.

## 5. Testing Impacts
- Update `tests/test_cli.py`, `tests/test_discovery_engine.py`, and `tests/test_e2e_flow.py` to mock or expect CodeGraph initialization rather than `indxr` and `ddd_context.json`.