# Design Document: Harness Initialization & Dynamic Discovery Redesign

**Status**: Draft (Pending User Approval)
**Date**: 2026-05-06
**Topic**: Refactoring `harness init` to use dynamic MCP discovery, fix directory structures, and deeply integrate Superpower workflows.

## 1. Problem Statement
The current `harness init` command relies on a static `INDEX.json` file to discover agents, which bypasses the powerful `CodeGraph` MCP server. Furthermore, the minting process duplicates directories (e.g., `_agents/agents`), omits required `agent.json` files for specialized agents, and does not deeply integrate the `superpowers` skills into the generated configurations or workspace rules.

## 2. Proposed Architecture: The 4-Stage Initialization

### Stage 1: Repository Bootstrap (Clone First)
Before performing any LLM operations, the CLI securely clones the `boilerplate-agent` from the remote `mapengbo0314/e2g` repository into a temporary staging directory.
- **Why?** This gives the CLI immediate access to the exact, up-to-date system prompts (e.g., `feature-fetcher/config.yaml`) defining the discovery logic, rather than hardcoding them in the Python CLI script.

### Stage 2: Dynamic Context Acquisition & Discovery (MCP)
- The CLI spawns an `CodeGraph serve --stdio` subprocess in the background.
- It acts as an MCP client to programmatically call the `summarize` tool on the project root (`.`) to acquire a fast, semantic snapshot of the repository.
- The CLI reads the `feature-fetcher` prompt from the staged boilerplate, appends the live MCP context, and sends it to the LLM (Gemini/Claude/OpenAI).
- The LLM returns a structured JSON list of specialized agents tailored to the project.

### Stage 3: Workspace Minting & Agent Generation
The temporary boilerplate is moved to the target project's `.agents/` directory. The internal `discovery` agents are pruned.

For each specialized agent discovered in Stage 2, the engine creates `.agents/agents/specialized/<agent_name>/` containing:
1. **`agent.json`**: The standard metadata manifest required by the host IDE/CLI to recognize the subagent.
2. **`config.yaml`**: A fully styled configuration mimicking the robust `core` agents. Crucially, it includes a **Superpower Workflow Integration** prompt section:
   - Example injected section: `"SUPERPOWER MANDATE: You MUST invoke relevant superpower skills (like writing-plans, brainstorming, test-driven-development) based on your task before executing. Check the available skills before responding."`

### Stage 4: Skills Integration & Documentation
- **Enriched Rules (`GEMINI.md` / `CLAUDE.md`)**: The minting engine writes a comprehensive rule file into the `.agents` (or project) root. This file will map the discovered agents, establish the general rules of the workspace, and explicitly mandate the usage of Superpower skills and the `CodeGraph` MCP.
- **Setup Script (`setup_harness.sh`)**: Generates a script that:
  1. Installs the Superpowers extension/plugin for the selected platform.
  2. Installs `CodeGraph` and configures the host IDE (e.g., `CodeGraph init --claude`).
  3. Executes `CodeGraph wiki generate` to seed the initial knowledge base.

## 3. Data Flow
1. `harness-wf init` -> `git clone` to `/tmp/e2g-boilerplate`
2. Run `CodeGraph serve --stdio` -> Call `summarize` -> Context string
3. Load `/tmp/e2g-boilerplate/.../feature-fetcher/config.yaml` + Context string -> Query LLM
4. Move `/tmp/.../boilerplate-agent` to `./.agents`
5. Generate `./.agents/agents/specialized/*/{config.yaml, agent.json}`
6. Write `./.agents/scripts/setup_harness.sh` and `./.agents/GEMINI.md`

## 4. Execution Guardrails & Cleanup
- **Legacy Script Cleanup**: The existing scripts in `boilerplate-agent/scripts/` (`clone_harness.py`, `clone_harness.sh`, and the static `setup_harness.sh`) are entirely obsolete. They will be deleted from the repository. The new `harness-wf init` command completely replaces the clone logic, and the `minting_engine.py` generates a dynamic `setup_harness.sh` file on the fly.
- **Timeouts**: None. The user explicitly requested removing the 60-second timeout.
- **Pruning**: Ensure `.agents/agents/discovery` is deleted post-discovery so internal tools do not clutter the final workspace.
- **MCP Config**: The generated `mcp.json` will include `--watch` and `--wiki-auto-update` to maintain wiki freshness.