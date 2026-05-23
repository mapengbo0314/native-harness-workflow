# Technical Design Document: Harness Init Architecture

**Status**: Finalized
**Topic**: True One-Click Onboarding and Workspace Scaffolding

## 1. Problem Statement

The "cold start" problem in setting up a new AI agent environment requires developers to manually perform configuration, scaffolding, and context-gathering. This introduces a high barrier to entry, increases friction, and often leads to misconfigured agent environments that lack deep project awareness. 

A unified `harness init` command is needed to provide a true one-click onboarding experience. It must automate the establishment of an Agentic Harness workspace by dynamically generating specialized subagents based on the existing codebase architecture, aligning the developer with Domain-Driven Design (DDD) boundaries, and injecting robust tool integrations such as auto-healing Model Context Protocol (MCP) servers and Superpower state machines. Core objectives include zero-manual configuration, context-aware agent generation without token explosion, and immediate readiness for work.

## 2. Proposed Design

The `harness init` architecture is cleanly separated into four distinct phases/engines that execute sequentially to ensure deterministic scaffolding and context preservation, while maximizing domain-aware specialization through a "Smarter Agents" feedback loop:

1. **CLI Entry & Orchestrator (`cli.py`)**: Acts as the outer shell handling arguments (`--project-path`, `--llm`, `--ddd`), interactive prompts, environment validation, and final execution of the auto-generated setup script.
2. **Context Engine (`discovery_engine.py::acquire_mcp_context`)**: A focused reader designed to avoid token bloat. Instead of traversing raw source code files recursively, it explicitly reads generated artifacts (`.codegraph/wiki/index.md` and `.codegraph/wiki/architecture.md`) to provide foundational knowledge to the LLM.
3. **Discovery Engine (`discovery_engine.py`)**: The LLM interaction layer. It incorporates a domain-first feedback loop:
    *   **DDD Onboarding & Grill**: The system extracts a drafted domain context and grills the user for alignment.
    *   **Grounded Agent Discovery**: The resulting `final_ddd_context` (ubiquitous language) is passed *into* the discovery prompt. The LLM uses this validated knowledge to natively specialize the 3-5 recommended agents' identities and system prompts.
    *   **Validation**: It utilizes strict JSON schema validation loops with a 3-retry minimum to guarantee valid outputs.
4. **Minting Engine (`minting_engine.py`)**: The robust filesystem generator. It scaffolds the workspace by cloning boilerplates, downloading required remote skills (e.g., `grill-with-docs`, `grill-me`), generating the auto-healing MCP server configurations (`codegraph serve --mcp`), dropping platform-specific rules directly into the workspace root, and instantiating the specialized agents.

## 3. Alternatives

During the design phase, several alternatives were considered and rejected:

*   **Recursive Source Code Scanning**: Rejected due to the risk of LLM context window explosions. Traversing the entire raw codebase tokenizes too much irrelevant data, leading to degraded LLM performance and higher costs. The chosen alternative is the Context Engine, which relies exclusively on high-level summarized knowledge from `.codegraph/wiki` artifacts.
*   **Static/Hardcoded Agent Roles**: Rejected because standardizing a generic set of agents (e.g., just "frontend" and "backend") fails to address the unique structural boundaries of diverse projects. The Discovery Engine's dynamic generation, now grounded in the `final_ddd_context`, creates specialized roles that match the exact architecture and ubiquitous language of the targeted codebase.
*   **Manual Dependency and MCP Configuration**: Rejected because relying on users to configure MCP server integration and download required Superpower skills manually defeats the "one-click onboarding" requirement and introduces points of failure. The Minting Engine automates this entirely, including auto-healing flags for `codegraph`.

## 4. Implementation

The following files will be updated to fulfill the proposed design:

*   **`harness/cli.py`**
    *   Update `parse_args` to capture necessary flags (`--project-path`, `--llm`, `--ddd`).
    *   Implement argument and environment variable validation (e.g., verifying API Keys exist without exposing them in history).
    *   Coordinate the sequential invocation of the Context, Discovery, and Minting engines.
    *   Execute the `setup_harness.sh` script automatically at the end of the initialization flow.

*   **`harness/discovery_engine.py`**
    *   Implement `acquire_mcp_context` to explicitly restrict reading to `.codegraph/wiki/index.md` and `.codegraph/wiki/architecture.md`.
    *   Implement `discover_ddd_context` to handle the interactive "DDD Alignment Grill" using Pocock skills when the `--ddd` flag is activated. This must execute *before* agent discovery to establish a shared domain model.
    *   Update `discover_agents` to accept the `final_ddd_context` as input, allowing the LLM to natively ground the generated agent identities and system prompts in the validated ubiquitous language.
    *   Update `query_llm` and `discover_agents` to use strict JSON schema validation for LLM outputs, incorporating a loop with at least 3 retries for malformed JSON.

*   **`harness/minting_engine.py`**
    *   Update `mint_workspace` to clone the core boilerplate into the target directory.
    *   Add functionality to download specified remote Superpower skills directly into `_agents/skills/`.
    *   Generate `mcp.json` with the exact command `codegraph serve --mcp` to ensure the MCP context remains self-healing.
    *   Write platform rules files (e.g., `GEMINI.md`, `CLAUDE.md`, `.cursorrules`) to the **root** project directory rather than the nested `.agents/` directory.
    *   Generate `setup_harness.sh` to install necessary prerequisites, and ensure the discovered agents (`system_prompt.md`, `agent.json`, `config.yaml`) are correctly serialized to disk.

## 5. Sphinch Marks

### Cross-Document Consistency
<!-- assert-category: cross-document-consistency -->
- [ ] The tools and components referenced (e.g., `codegraph`) match the definitions in other system workflows and the `CLI` modules.

### Interface Accuracy
<!-- assert-category: interface-accuracy -->
- [ ] The generated `mcp.json` contains the exact command arguments `codegraph serve --mcp`.

### State Machine Completeness
<!-- assert-category: state-machine-completeness -->
- [ ] The `setup_harness.sh` script is automatically executed by the CLI entry script upon successful minting.
- [ ] The JSON validation loop correctly implements a bound of minimum 3 retries before failing, ensuring no infinite parsing loops.

### Failure Mode Coverage
<!-- assert-category: failure-mode-coverage -->
- [ ] The LLM response parser correctly triggers a failure mode and recovers or alerts the user if JSON schema validation fails 3 times.

### Dependency Declarations
<!-- assert-category: dependency-declarations -->
- [ ] **Context Engine Boundaries**: The context engine ONLY reads `.codegraph/wiki/index.md` and `.codegraph/wiki/architecture.md` (it must not recursively read source code).
- [ ] **Root Rule Placement**: The platform rules file (e.g., `GEMINI.md`) is successfully generated in the project root, not hidden within the `.agents/` folder.
- [ ] **Skill Localization**: Remote Superpower skills are downloaded and stored locally in the `_agents/skills/` directory.
