# Design Document: Harness Initialization CLI (`harness init`)

**Status**: Finalized (Pending User Approval)
**Date**: 2024-05-06
**Topic**: Streamlining Stage 0 of the Agentic Harness Lifecycle.

## 1. Problem Statement
The current "Stage 0: Bootstrap & Minting" process is fragmented. A developer must manually run an indexer, then run a discovery script, then run a cloning script. This creates friction and increases the likelihood of configuration errors. We need a single, unified entry point that guides the developer from a raw repository to a fully-functioning, specialized agent workspace equipped with MCP access to the codebase context.

## 2. Proposed Solution: The `harness init` Command
A unified CLI command that orchestrates the entire bootstrap process with a focus on security, flexibility, interactive refinement, and MCP integration.

### Command Syntax
```bash
harness init \
  --project-path <path_to_repo> \
  --llm <gemini|openai|anthropic> \
  [--bundle <path_to_existing_index>]
```

### Execution Flow
1. **Security & Pre-flight**
   - **Credential Check**: If `API_KEY` (e.g., `GEMINI_API_KEY`) is missing from environment, use a secure hidden prompt (`getpass`) to acquire it.
   - **Tool Check**: Verify `CodeGraph` is on the system `PATH`. If missing, halt and provide installation instructions.

2. **Context Acquisition (The Fork)**
   - If `--bundle` is provided, validate the existing index.
   - Otherwise, execute `CodeGraph index -f json` on `--project-path`.
   - Generate `metadata.json` with a timestamp to satisfy the **Stale Index Gate**.

3. **AI-Driven Agent Discovery**
   - **Pruning**: Extract a structural map (directory tree max 3 levels + core file summaries) to stay within LLM context limits.
   - **Flexible Discovery**: Instead of fixed tiers, the LLM is prompted to:
     1. Analyze the project's specific architecture (e.g., MVC, Microservice, Library).
     2. Identify 3-5 logical "specialization zones".
     3. Recommend an agent for each zone with a specific role and toolset.

4. **Human-in-the-Loop (HITL) TUI**
   - Use a terminal prompt loop to:
     - Multi-select from recommended agents.
     - Inline edit agent names or descriptions.
     - Manually add custom agents.
   - **Platform Selection**: Prompt the user to select their target AI environment (e.g., Gemini CLI, Claude Code, Cursor) to tailor the prerequisite installations.
   - Proceed only upon explicit confirmation.

5. **Workspace Minting & Setup Prerequisites**
   - Clone `boilerplate-agent/` to `./.agents/` (stripping `.git`, logs, and caches).
   - Inject `agent.json` and `config.yaml` for each selection.
   - **Platform Setup Script**: Generate a customized `scripts/setup_harness.sh` based on the selected platform. This handles prerequisites: installing specific CLI skills/extensions AND installing `CodeGraph` with `wiki,http` features.
   - **MCP Onboarding**: Automatically inject the `CodeGraph serve` command into the workspace's global `mcp.json` and bind it to the minted agents.
   - Run an environment audit and print a "Next Steps" checklist.

## 3. Component Architecture
- **`harness/cli.py`**: Main entry point using `argparse`.
- **`harness/indexer_wrapper.py`**: Invokes `CodeGraph` and standardizes output.
- **`harness/discovery_engine.py`**: Manages LLM prompts and parses recommendation JSON.
- **`harness/minting_engine.py`**: Handles boilerplate cloning, config injection, and setup script generation.

## 4. Security & Credentials
- **NO `--key` FLAG**: Secrets are NEVER passed as command arguments to prevent shell history leakage.
- **Memory-only**: API keys are kept in memory for the duration of the command and NEVER written to the minted workspace.
