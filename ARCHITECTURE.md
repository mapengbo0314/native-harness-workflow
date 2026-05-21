# Superpowers Agentic Harness: Architecture & Workflow

The Superpowers Agentic Harness operates on a **Hub-and-Spoke** model where the "Hub" is the **Orchestrator** (Router) and the "Spokes" are **Specialized Agents** tailored to your specific codebase. This architecture is powered by `CodeGraph` for codebase semantic mapping and the Superpowers skill lifecycle for deterministic execution.

## 1. Lifecycle Phase 1: Discovery & DDD Alignment

Before the harness is minted, the `discovery_engine` must understand your domain without exhausting token windows.

- **CodeGraph Wiki Bundle**: The process begins with a pre-generated `.codegraph/wiki` bundle (created by the user). The discovery engine uses this as a read-only semantic map to index symbols and summaries without reading raw code.
- **Dynamic Skill Onboarding**: To rigorously analyze the domain, the engine dynamically fetches remote evaluation and prompt skills (e.g., `agentic-eval`, `prompt-engineer`, `grill-with-docs`) directly from trusted URLs. These are used to self-critique the generated agents and domain context.
- **DDD Alignment**: By combining the wiki data with these dynamic skills, the engine identifies ambiguities and generates Domain-Driven Design (DDD) "Grill" questions. Your answers are woven into a robust **DDD Context** (`ddd_context.json`).
- **Feature Fetching**: A specialized LLM routine uses this DDD context to recommend 3-5 specialized agents (e.g., `trust-agent`, `api-specialist`) with comprehensive, project-specific system prompts.

## 2. Lifecycle Phase 2: Minting & Setup

The `minting_engine` takes the output of Discovery and creates a platform-specific environment ready for use.

- **Workspace Minting**: The engine creates a hidden directory (e.g., `.gemini/`, `.claude/`) containing the Orchestrator, specialized agents, workflow rules, and a local copy of core skills.
- **Permanent Skill Onboarding**: The engine generates a `setup_harness.sh` script. When executed, this script installs the core `superpowers` and `skills` extensions permanently into your chosen AI environment.
- **MCP Registration**: The `setup_harness.sh` script automatically registers the `CodeGraph` MCP server with your AI platform (Gemini, Claude, or Cursor). This transitions the harness from the "read-only wiki" discovery state to a "live, tool-enabled" runtime state.

## 3. Lifecycle Phase 3: Final User State

After the `minting_engine` runs, you have a fully customized, context-aware environment.

- **The Entryway**: A platform-specific pointer file (e.g., `GEMINI.md`, `CLAUDE.md`, `.cursorrules`) is dropped into your root directory to act as the harness entry point.
- **Activation**: To start, simply run the generated `setup_harness.sh`, reload your AI platform (e.g., `/mcp reload` in Gemini), and the Orchestrator will automatically assume control.
- **Dynamic Dispatch**: The harness includes dynamic routing rules that automatically send tasks to your specialized domain agents based on the context of your request.

## 4. Runtime Workflow

Once activated, the daily execution flow is strictly enforced:

1. **Orchestrate**: The AI assumes the **Orchestrator** role defined in your harness.
2. **Analyze**: For any task, the Orchestrator uses the live **CodeGraph MCP** to search the codebase (e.g., `summarize`, `get_public_api`).
3. **Delegate**: The Orchestrator follows the **Zero-Work Rule**, delegating research to the `architect` or implementation to specialized agents.
4. **Implement**: Tasks are handed to the `implementer`, which **MUST** use the `test-driven-development` skill.
5. **Verify**: The `verifier` or `adversary` agent ruthlessly checks the output against the original plan before completion.

---

## File Structure Comparison

| Platform | Root Pointer | Harness Directory | Setup Script |
| :--- | :--- | :--- | :--- |
| **Gemini CLI** | `GEMINI.md` | `.gemini/` | `.gemini/scripts/setup_harness.sh` |
| **Claude Code** | `CLAUDE.md` | `.claude/` | `.claude/scripts/setup_harness.sh` |
| **Cursor** | `.cursorrules` | `.cursor/` | `.cursor/scripts/setup_harness.sh` |

### Common Harness Sub-structure
```text
.gemini/
├── AGENTS.md (Rules)
├── orchestrator.md (Role)
├── mcp.json (Config)
├── agents/ (Specialized Spokes)
│   ├── trust-agent.md
│   ├── api-specialist.md
│   ├── planner.md
│   ├── implementer.md
│   └── verifier.md
├── rules/ (State Machine)
│   ├── dispatch_rules.md
│   └── unified_superpower_workflow.md
├── skills/ (Local Superpowers)
├── ddd/ (Domain Context)
│   ├── context.md
│   └── translation_map.json
└── scripts/ (setup_harness.sh)
```
