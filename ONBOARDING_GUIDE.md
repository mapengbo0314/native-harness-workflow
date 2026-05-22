# User Guide: Onboarding a New Repository with Harness-WF

This guide explains how to ground a completely new project into the Superpowers Agentic Harness using an existing `CodeGraph` bundle.

## Overarching Architecture & Workflow

The Harness-WF operates on a **Hub-and-Spoke** model where the "Hub" is the **Orchestrator** (Router) and the "Spokes" are **Specialized Agents** tailored to your specific codebase.

### 1. Discovery & Alignment (The Brain)
- **CodeGraph Wiki**: Before initialization, `CodeGraph` generates a semantic map (`.codegraph/wiki/`).
- **DDD Alignment Grill**: The CLI uses this wiki to identify ambiguities and asks you "Grill" questions. Your answers are woven into the identity of every agent generated.
- **Feature Fetcher**: A specialized LLM routine analyzes the wiki and your DDD answers to recommend 3-5 agents (e.g., `trust-agent`, `api-specialist`) with comprehensive system prompts.

### 2. Minting (The Body)
The `mint_workspace` engine creates a platform-specific hidden directory (e.g., `.gemini/`) and populates it with:
- **`agents/`**: Markdown definitions for the Orchestrator and specialized agents.
- **`rules/`**: The strictly deterministic workflow state machine (Brainstorming -> Planning -> TDD -> Implementation -> Verification).
- **`skills/`**: Local copies of Superpower skills.
- **`mcp.json`**: Configuration that connects the AI to the `CodeGraph` server.

### 3. Root Pointers (The Entryway)
A platform-specific file is dropped into the root of your project:
- **Gemini CLI**: `GEMINI.md` (uses `@.gemini/orchestrator.md` inclusion syntax).
- **Claude Code**: `CLAUDE.md` (Markdown link/pointer).
- **Cursor**: `.cursorrules` (Instructions to use the harness).

### 4. Runtime Workflow
1. **Launch**: You start your AI (e.g., `gemini`). It automatically loads the root pointer.
2. **Orchestrate**: The AI assumes the **Orchestrator** role defined in `.gemini/orchestrator.md`.
3. **Analyze**: For any task, the Orchestrator uses the `CodeGraph` MCP to search the wiki first.
4. **Delegate**: The Orchestrator **Zero-Work Rule** kicks in; it delegates to `architect` for research or `planner` for roadmapping.
5. **Implement**: Tasks are handed to `implementer`, which **MUST** use the `test-driven-development` skill.
6. **Verify**: The `verifier` or `adversary` agent ruthlessly checks the output against the original plan before completion.

---

## Prerequisites
- `harness-wf` installed (`pip install -e .` from this repo root).
- `CodeGraph` CLI installed and configured.
- Your project directory (e.g., `~/my-awesome-app`).

---

## Step 1: Pre-generate the Codebase Index (CodeGraph Bundle)
Before running the harness, we utilize the `CodeGraph` tool to create a semantic map of your repository.

```bash
# 1. Navigate to your project
cd ~/my-awesome-app

# 2. Set your LLM API Key (CodeGraph uses this to process the code)
export ANTHROPIC_API_KEY="sk-..." 

# 3. Generate the wiki bundle
CodeGraph wiki generate {my-awesome-app}
```

This creates a hidden `.codegraph/` folder in your project root containing the full knowledge base of your codebase.

---

## Step 2: Initialize the Agentic Harness
Run the `harness-wf` tool to mint your agents and platform-specific pointers. Use the `--bundle` flag to point to the existing index so the harness can instantly understand your repo.

```bash
# Initialize the harness using Gemini as the orchestrating LLM
# and the existing index for context
harness-wf init --project-path . --llm gemini --bundle .codegraph
```

### What to expect:
- **DDD Alignment**: The CLI will grill you with Domain-Driven Design questions based on your code to align the agents' terminology with your business logic.
- **Agent Discovery**: The "Feature Fetcher" analyzes your index and recommends specialized agents (e.g., `trust-agent`, `auth-expert`) tailored to your project.
- **Platform Selection**: You will choose a target platform (Gemini CLI, Claude Code, or Cursor).
- **Pointer Generation**: A root-level pointer (e.g., `GEMINI.md`, `CLAUDE.md`, or `.cursorrules`) will be dropped into your project root. This file uses the `@include` syntax for Gemini to automatically load the harness.
- **Clean Workspace**: The tool will automatically prune unused platform directories to keep your repo clean.

---

## Step 3: Platform Setup
Once the minting is finished, run the setup script for the specific tool you selected.

### If using Gemini CLI:
```bash
sh .gemini/scripts/setup_harness.sh
```

### If using Claude Code:
```bash
sh .claude/scripts/setup_harness.sh
```

### If using Cursor:
```bash
sh .cursor/scripts/setup_harness.sh
```

---

## Success!
Your repository is now fully grounded. When you launch your AI (e.g., `gemini`), it will read the root pointer, follow it to the hidden platform folder (e.g., `.gemini/orchestrator.md`), and assume the **Orchestrator** role. 

From there, it will follow the mandated Superpower workflows (Brainstorming -> Planning -> TDD -> Implementation -> Verification) and delegate tasks to the specialized agents it discovered for your project.
