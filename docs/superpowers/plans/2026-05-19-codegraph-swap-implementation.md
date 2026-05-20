# CodeGraph MCP Full Swap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy `indxr` and `ddd_context` modules with `@colbymchenry/codegraph` as the exclusive context engine. Implement the Direct-Dispatch Matrix, merge orchestrator rules, and introduce the CLI Context Wizard with "Ghost Injection."
**Architecture:** Archive legacy functions, verify Node.js prerequisites, initialize CodeGraph DB, swap MCP configuration, merge `dispatch_rules.md` into `orchestrator.md`, deprecate and delete the `@architect` agent, and update remaining agent templates.
**Tech Stack:** Python, Bash, Agent Markdown Profiles, `@colbymchenry/codegraph`.

---

### Task 1: Archive Legacy NLP & DDD Modules and Cleanup Dependencies

**Files:**
- Create: `archive/legacy_indxr/__init__.py`
- Modify: `harness/discovery_engine.py`
- Modify: `harness/cli.py`
- Modify: `harness/minting_engine.py`
- Modify: `requirements.txt`
- Modify: `pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Create archive directory and ignore it**

```bash
mkdir -p archive/legacy_indxr
echo "archive/" >> .gitignore
touch archive/legacy_indxr/__init__.py
```

- [ ] **Step 2: Ignore CodeGraph Database**

Ensure the ephemeral CodeGraph database is never committed:
```bash
echo ".codegraph/" >> .gitignore
```

- [ ] **Step 3: Relocate legacy functions**

Move the `discover_ddd_context` function from `harness/discovery_engine.py` into a new file `archive/legacy_indxr/ddd_discovery.py`.
Remove the function definition and its imports from `harness/discovery_engine.py`.

- [ ] **Step 4: Remove DDD extraction from `cli.py`**

In `harness/cli.py`, remove the automated LLM DDD extraction block (calls to `discover_ddd_context`, `run_ddd_grill`, and the `--ddd` argument). Do not delete the `mint_workspace` call.

- [ ] **Step 5: Remove DDD generation from `minting_engine.py`**

In `harness/minting_engine.py` (`mint_workspace` function), remove logic that saves `ddd_context.json` and writes `ddd/context.md` / `ddd/translation_map.json`.
Remove `ddd_context` arguments from helper functions.

- [ ] **Step 6: Clean up Python Dependencies**

Open `requirements.txt` and `pyproject.toml`.
Find and remove any dependencies explicitly related to `indxr` or the old semantic wiki parser.

### Task 2: CodeGraph CLI Onboarding & Prerequisites

**Files:**
- Modify: `harness/cli.py`

- [ ] **Step 1: Check for Node.js / npx prerequisite**

In `harness/cli.py` (during initialization/setup), add a check to ensure `npx` is available in the system PATH before attempting to run CodeGraph commands.

```python
    import shutil
    if not shutil.which("npx"):
        print("\\nError: 'npx' command not found. Node.js is required to use CodeGraph.")
        sys.exit(1)
```

- [ ] **Step 2: CLI Context Wizard (The 3 Questions)**

In `harness/cli.py`, implement the new CLI Wizard to collect project invariants from the user during initialization. **Crucially, place this block exactly where the old `--ddd` argument logic used to be (right before `mint_workspace` is called).**

```python
    print("\\n--- Project Context Setup ---")
    purpose = input("1. In 1-2 sentences, what is the core purpose of this project?\\n> ")
    vocab = input("2. What are 2-3 specific vocabulary terms (Ubiquitous Language) used in this codebase?\\n> ")
    invariants = input("3. Are there any strict architectural rules or invariants? (e.g., 'Never delete users, only deactivate')\\n> ")
    
    # Save to docs/domain/CONTEXT.md
    context_dir = os.path.join(args.project_path, "docs", "domain")
    os.makedirs(context_dir, exist_ok=True)
    with open(os.path.join(context_dir, "CONTEXT.md"), "w") as f:
        f.write(f"# Project Context\\n\\n## Purpose\\n{purpose}\\n\\n## Ubiquitous Language\\n{vocab}\\n\\n## Strict Invariants\\n{invariants}\\n")
```

- [ ] **Step 3: Auto-Initialize CodeGraph DB**

Replace the old `indxr` bundle resolution logic with a check for CodeGraph:

```python
    codegraph_db_path = os.path.join(args.project_path, ".codegraph", "codegraph.db")
    if not os.path.exists(codegraph_db_path):
        print(f"\\nCodeGraph database not found. Building now...")
        try:
            subprocess.run(
                ["npx", "-y", "@colbymchenry/codegraph", "init", "--index"],
                cwd=args.project_path,
                check=True
            )
        except subprocess.CalledProcessError as e:            print(f"\\nFailed to build CodeGraph: {e}")
            sys.exit(1)
```

### Task 3: MCP Configuration & Guaranteed Skills

**Files:**
- Modify: `harness/minting_engine.py`
- Modify: `boilerplate-agent/onboarding/tools.json` (or equivalent skills registry)

- [ ] **Step 1: Swap indxr for CodeGraph in `mcp.json` templates**

In `harness/minting_engine.py`, replace `indxr` commands with `codegraph`:
For Gemini: `gemini mcp add codegraph npx -y @colbymchenry/codegraph mcp || true`
For Claude: `claude mcp add --scope project codegraph -- npx -y @colbymchenry/codegraph mcp || true`
Update the `mcp_config` JSON template to use the new CodeGraph command.

- [ ] **Step 2: Update `AGENTS.md` and tools lists**

In `harness/minting_engine.py`, change `mcp_servers: ["indxr"]` to `mcp_servers: ["codegraph"]`.
Update the agent tools string to include the correct CodeGraph tools (e.g., `codegraph_search`, `codegraph_explore`, `codegraph_context`, `codegraph_callers`, `codegraph_impact`), while retaining `grep_search` / `Grep` for non-symbol text targets (like UI strings).

- [ ] **Step 3: Force `grill-with-docs` installation**

Update the skills registry (e.g., `boilerplate-agent/onboarding/tools.json`) to mark `grill-with-docs` as required.
In `minting_engine.py`, ensure the logic downloads and provisions this skill unconditionally for the workspace.

### Task 4: Orchestrator Merge and Direct-Dispatch Matrix

**Files:**
- Modify: `boilerplate-agent/orchestrator.md`
- Delete: `boilerplate-agent/rules/dispatch_rules.md`

- [ ] **Step 1: Merge `dispatch_rules.md` into `orchestrator.md`**

Open `boilerplate-agent/rules/dispatch_rules.md`. Copy ONLY the `<core_mandates>` XML block and the specific tool restrictions. Paste these directly into the `### CORE MANDATES` section of `boilerplate-agent/orchestrator.md`.
Delete `boilerplate-agent/rules/dispatch_rules.md` to prevent secondary file-read anti-patterns.

- [ ] **Step 2: Implement Direct-Dispatch Decision Matrix and Eval Block**

In the new unified `orchestrator.md`, replace the 5-phase waterfall with the Direct-Dispatch branches defined in the design spec (Branch A: Bug Fix, Branch B: Feature, Branch C: Q&A, Branch D: Surgical Edit).
Crucially, enforce the mandatory JSON Eval Block in the system prompt:

```markdown
Before using ANY tool or dispatching ANY subagent, you MUST output a structured evaluation block exactly like this:
\`\`\`json
{
  "intent_analysis": "Explanation of user intent",
  "selected_branch": "Branch A, B, C, or D",
  "required_tools": ["codegraph_search", "grep_search", etc.],
  "dispatch_target": "@implementer, @planner, or None"
}
\`\`\`
```

- [ ] **Step 3: Embed the Golden Rule**

Inject the CodeGraph Golden Rule into `orchestrator.md`:
"**THE GOLDEN RULE:** Call the MCP tool (`codegraph_*`) to gather precise context instead of reading full files, unless absolutely necessary (e.g., using `grep_search` for UI strings)."

### Task 5: Agent Prompts, Ghost Injection & Architect Deprecation

**Files:**
- Delete: `boilerplate-agent/agents/architect.md`
- Delete: `.gemini/agents/architect.md` (and equivalent platform folders if present)
- Modify: `boilerplate-agent/agents/*.md`
- Modify: `harness/minting_engine.py`

- [ ] **Step 1: Delete the Architect Agent**

Remove the `architect.md` file from `boilerplate-agent/agents/`.
Also remove it from any active workspace agent directories (e.g., `.gemini/agents/`, `.claude/agents/`).
In `harness/minting_engine.py`, ensure the Architect is removed from any agent generation lists or tool configurations if it was hardcoded.

- [ ] **Step 2: Sub-Delegation Authority for Planner & Implementer**

Update `boilerplate-agent/agents/planner.md` and `implementer.md`. Provide them explicit instructions and authority to delegate verification and review tasks.
For `@planner`: "Once the plan is drafted, you MUST delegate it to `@reviewer` for validation before finalizing. You are responsible for all architectural mapping and dependency analysis."
For `@implementer`: "Once code is written, you MUST delegate verification to `@verifier` and style/quality checks to `@reviewer` or `@linter-agent`."

- [ ] **Step 3: Update remaining Agent Prompts**

For all remaining files in `boilerplate-agent/agents/`, replace "Wiki-First strategy" and `mcp_indxr_*` with the "Graph-First strategy" and `codegraph_*` tools. Ensure `grep_search` remains available. Embed the Golden Rule.

- [ ] **Step 4: Implement Ghost Injection**

In `harness/minting_engine.py`, during the generation of the `implementer.md` file for a specific workspace:
**Graceful Fallback:** First, check if `docs/domain/CONTEXT.md` exists. If it does not exist (e.g. the user bypassed the CLI Wizard), generate a default `CONTEXT.md` with empty sections.
Read the contents of `docs/domain/CONTEXT.md` (specifically the "Strict Invariants" section).
Append these strict invariants dynamically to the bottom of the `@implementer` agent's system prompt to enforce architectural rules on fast-path edits.

### Task 6: CI/CD & Testing Impacts

**Files:**
- Delete: `.github/workflows/update-indexer.yml`
- Create: `.github/workflows/codegraph-ci.yml`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_discovery_engine.py`
- Modify: `tests/test_e2e_flow.py`

- [ ] **Step 1: Update CI/CD for CodeGraph**

Delete the old `.github/workflows/update-indexer.yml`. 
Create `.github/workflows/codegraph-ci.yml`. Since CodeGraph generates an ephemeral local database, we don't commit it. The CI workflow should simply verify that CodeGraph can build successfully or build it as a prerequisite step for automated AI reviewers.

```yaml
name: CI CodeGraph Build Check
on: [push, pull_request]
jobs:
  build-graph:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Build CodeGraph
        run: npx -y @colbymchenry/codegraph init --index
```

- [ ] **Step 2: Align Test Suite**

Update `tests/test_cli.py` to mock `shutil.which` (returning a valid path) and mock `builtins.input` with a `side_effect` list to handle the new CLI Wizard questions.
Remove outdated tests in `tests/test_discovery_engine.py` and `tests/test_e2e_flow.py` that check for `ddd_context.json` or `.indxr`.
Add tests ensuring `CONTEXT.md` is created correctly and that Ghost Injection appends to the implementer's prompt.

- [ ] **Step 3: Verify Tests**

```bash
pytest tests/ -v
```
