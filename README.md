# Superpowers Agentic Harness

Welcome to the **Superpowers Agentic Harness** – a strictly orchestrated, graph-driven agentic framework designed to scale intelligence safely across the codebase.

This repository relies on a robust **Orchestrator** mechanism equipped with pre-tool hooks, state-machine workflows (Skills), and highly specialized Subagents. By strictly bounding operations to clear **Lane Views (Routing Branches)** and enforcing a **Graph-First Strategy** for context gathering, the harness protects system integrity while executing complex engineering tasks.

---

## 🚀 Installation & Usage

### Installing `harness-wf`

The Harness is distributed as a Python CLI tool designed to be installed locally.

First, clone this repository to your local machine:

```bash
git clone https://github.com/mapengbo0314/native-harness-workflow.git
cd native-harness-workflow
```

Then, install it in editable mode using `pip` or `uv`:

```bash
uv pip install -e .
# or
pip install -e .
```

### Minting a Workspace (`init`)

To apply the Harness to a target project, run the `init` command from anywhere:

```bash
harness-wf init --project-path /path/to/your/project
```

To enable optional [RTK](https://github.com/rtk-ai/rtk) shell-output
compression, add `--rtk`. Interactive setup offers to install RTK when it is
missing:

```bash
harness-wf init --project-path /path/to/your/project --rtk
```

For headless or CI setup, explicitly authorize installation:

```bash
harness-wf init --project-path /path/to/your/project --install-rtk
```

Without either flag, RTK is never checked, installed, or configured. If RTK
installation fails, harness setup warns and continues without it.

**What this does:**

1. **Scaffolds the Environment:** Creates the `.gemini/` (or `.claude/`, etc.) directory in your project containing the necessary Orchestrator configurations, subagents, and hooks.
2. **Installs Skills:** Copies the state-machine workflow definitions (`SKILL.md` files) into the target project.
3. **Sets up CodeGraph MCP:** Automatically registers the `codegraph` MCP server in your CLI's configuration file, giving the AI immediate structural awareness of your codebase.
4. **Optionally configures RTK:** With `--rtk`, adds RTK usage rules and installs a project-level Claude `PreToolUse` hook when supported.
5. **Scaffolds the Project-Ops Manifest:** Detects your stack and creates `domain.json` under the platform's deployed root, and registers the `domain` MCP server so agents can pull real repo operations via `domain_ops(topic)` (see below).

### Project-Ops Manifest (`domain.json`)

The manifest holds the repo's *real* operational knowledge — `stack`,
`environments`, `test`, `deploy`, `infra`, `references`, `business` — and is
served to agents at runtime by the `domain` MCP server's single pull tool,
`domain_ops(topic)`. Agents consult it before build/test/deploy work instead
of guessing commands, and the `business` digest is injected on planning and
question branches.

`init` detects the stack automatically. Finishing the setup is **two steps**:

1. **Drop your product docs** (PRD, direction, business goals) into your
   platform's reference dir — `.claude/docs/reference/` for a Claude mint
   (`.gemini/docs/reference/` etc. for embedded platforms).
2. **Compile them** into the manifest's `business` section:

   ```bash
   harness-wf domain-compile --project-path . --platform claude
   ```

   Requires a `claude` or `gemini` CLI on PATH. Re-run whenever the docs
   change — a failed compile never wipes a previously compiled section.

Fill the `environments` / `test` / `deploy` / `infra` slots by hand (they are
scaffolded empty), and re-detect the stack after it changes:

```bash
harness-wf domain-refresh --project-path .
```

`domain.json` is **user-owned**: re-running `init` never clobbers it and
`harness-wf update` never touches it. Schema reference:
[`.claude/docs/domain/domain.schema.md`](.claude/docs/domain/domain.schema.md).

---

## 🚦 Orchestration & Lane Views (Matrix Routing)

The core `OrchestratorDispatcher` categorizes incoming prompts using an LLM-assisted or fallback keyword-matching mechanism into four strict routing branches. This prevents the "generalist" context-bloat and enforces deterministic boundaries for each phase of work:

- **Branch A: Bug Fix & Diagnosis (`@diagnose`)**
  Focuses on stack traces, errors, and breakages. The agent is strictly **read-only** at this phase and must isolate the error using structural graph tools (`codegraph_callers`) to emit a diagnosis report before moving to resolution.
- **Branch B: Feature Request & Architectural Planning (`@planner` → `@implementer`)**
  Focuses on creation and implementation. Work is routed to `@planner` which operates in a read-only + web-search sandbox to draft design documents. Only upon design approval is the task handed over to the `@implementer` agent with Full FS/Git access.
- **Branch C: Codebase Questioning & Knowledge Retrieval (`@generalist`)**
  Focuses on understanding. Agents operating in this lane are **STRICTLY UNAUTHORIZED** to mutate files and rely entirely on mapping the domain.
- **Branch D: Surgical Edit / Fast Path (`@implementer`)**
  When minor changes (typos, color changes) are requested, the harness overrides heavy planning workflows, authorizing immediate, bounded modifications to bypass the heavy `@planner` phase.

---

## 🤖 The Subagent Roster

The framework compartmentalizes capabilities into explicitly defined, highly restrictive agents to limit blast radius and ensure quality:

- **`@planner`**: Reads the codebase, queries the CodeGraph, searches the web, and produces design documents in `docs/designs/`. Cannot write production code.
- **`@implementer`**: Executes TDD implementation based entirely on approved plans. Writes to `docs/progress/` and manages blockers. Does not solicit reviews directly; fails fast.
- **`@reviewer`**: Senior evaluator agent. Assesses code against the planned designs. Strictly read-only; appends blocking feedback but does not rewrite the code.
- **`@adversary`**: The hyper-skeptical stress-tester. Dedicated to hunting edge cases, invalidating assumptions, and enforcing resilience without flattery or hallucinations.
- **`@diagnose`**: Runs the read-only triage phase of Branch A to systematically identify the root cause of regressions or bugs.
- **`@generalist`**: Bound by Branch C rules (read-only) for questions or Branch D rules for fast-path surgical edits.

---

## 🧠 Our Context: The Graph-First Strategy

To prevent token exhaustion and provide massive codebase comprehension, this harness natively integrates the **CodeGraph MCP Server**. Agents are mandated to employ a tiered **Graph-First Strategy** before attempting to blindly read source files:

1.  **Level 1 (Discovery)**: `codegraph_explore` maps folder topologies; `codegraph_search` identifies exact symbol locations.
2.  **Level 2 (Understanding)**: `codegraph_context` retrieves definitions and nearby context; `codegraph_callers` traces code usage paths.
3.  **Level 3 (Impact Analysis)**: `codegraph_impact` evaluates the downstream blast radius before any structural code changes are proposed.
4.  **Level 4 (Raw Read)**: Standard `read_file` operations are treated as a last resort, strictly reserved for actively mutating logic or reading non-structural strings. You MUST attempt to read specific logic using `codegraph_node(includeCode=true)` before falling back to reading the entire file.

### Engineering & Domain Invariants

- **Python-First Base**: Current services heavily emphasize Python, utilizing explicit imports, composable functions, and dataclasses.
- **Progressive JVM Migration**: The environment is actively preparing translation bounded subsystems to Kotlin/Java.
- **Zero UI Prototyping**: The harness strictly forbids visual/UI driven architectural brainstorming in favor of text/code-centric designs.

---

## ⚡ Superpower Skills

The harness uses a rigorous State Machine of "Skills" to inject workflow discipline before an agent is allowed to act.

Whenever an intent is received, the agent **MUST** invoke relevant skills (found in `.gemini/skills/`). Some key workflows include:

- **`using-harness-superpowers`**: The master gatekeeper. Enforces the priority of skills over default prompts.
- **`harness-brainstorming-plans`**: Bypasses UI prototyping, forces text-based architectural alignment.
- **`harness-test-driven-development` / `tdd`**: Red-Green-Refactor enforcement.
- **`verification-before-completion`**: The mandatory final check before an agent can conclude a task.

---

## 🛡️ Hooks & System Protections

The orchestrator sits atop robust system-level hooks that intercept agent actions prior to execution, providing a deterministic layer of security:

- **Pre-Tool Use Sandbox (`pre_tool_use.py`)**:
  Intercepts any tool execution request and evaluates it for catastrophic actions.
  - **Anti-Destruction**: Regex heuristics block dangerous bash commands like `rm -rf /` or wildcard recursive deletions before they hit the shell.
  - **Secret Protection**: Explicitly blocks file tools or bash commands from touching `.env` files (except safe `.env.sample` templates) to prevent credentials from entering the LLM context or logs.
- **Langfuse Telemetry**: Native, deeply integrated observation traces (`@observe`). Intent classification, phase calculation, and model selection are tracked via environment injection to ensure full auditability of agent performance.

---

## 🔭 Observatory Dashboard

The engineering intelligence dashboard has been migrated into this repository under `observatory/`. It tracks harness adoption status, AI commit percentages, rework rates, and commit sizes across repositories.

Personal configuration files (`repos.yaml`, `mailmap.yaml`) are explicitly ignored by Git. Example templates are provided. The dashboard uses the `indxr` executable on your `$PATH` to calculate code health hotspots with graceful degradation if it is missing.

For a comprehensive guide on interpreting the dashboard, please see [`observatory/METRICS.md`](observatory/METRICS.md).

### Setup

```bash
cd observatory
cp repos.yaml.example repos.yaml
cp mailmap.yaml.example mailmap.yaml
# Fill in your repos and GITHUB_TOKEN in observatory/.env
npm install
npm run dev
```

---

## 🔄 Updating the Harness

As new workflows, skills, or prompt templates are added to the harness, you can update an existing project without losing your local customizations using the `update` command.

From the root of your project:

```bash
# Preview what would be updated (dry-run)
harness-wf update --project-path . --check

# Apply the update
harness-wf update --project-path .

# Force overwrite any locally modified files that are conflicting
harness-wf update --project-path . --force

# For older Claude plugins without a tracking manifest, generate one first
harness-wf update --project-path . --adopt
```

_(Note: Automated in-place updates are currently only fully supported for the Claude Code plugin structure. Other platforms require re-running `harness-wf init` to re-mint the workspace.)_

### For Harness Maintainers

When modifying the core harness files in `src/harness` or `src/harness/templates`:

1. You **must** bump the `version` field in the root `pyproject.toml`. The updater uses the package version to determine if a project is out-of-date.
2. Ensure you add your changes to the templates so that `harness-wf update` can correctly calculate diffs during the next deployment.
