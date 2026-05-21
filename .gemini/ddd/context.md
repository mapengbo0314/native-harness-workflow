# E2G Agentic Harness - Core Domain Context

## 1. Ubiquitous Language (Glossary)

*   **Harness**: The overarching stateless utility system responsible for bootstrapping and analyzing codebases.
*   **Workspace**: A generated, project-specific environment created by the Minting Engine. *Ambiguity: Is this just a file directory artifact, or a runtime entity?*
*   **Agent**: An actor in the system, exclusively defined by a standalone Markdown document (e.g., `architect.md`). It encapsulates instructions and mandates but lacks native executable code.
*   **Skill**: An atomic, executable capability (e.g., `grill-me.md`) that an Agent can utilize. Can be local to the boilerplate or fetched dynamically (`fetch_remote_skill`).
*   **Discovery Engine**: The sub-domain responsible for analyzing external codebases to recommend Agent configurations and extract domain intelligence.
*   **Minting Engine**: The sub-domain responsible for projecting Discovery outputs and Boilerplate Templates into a concrete Workspace.
*   **Boilerplate Template**: The immutable source truth (`boilerplate-agent/`) used as the structural foundation during Minting.
*   **Context (WARNING: Overloaded)**: Currently used interchangeably to mean Domain-Driven Design context (`discover_ddd_context`), LLM context windows, and Model Model Context Protocol state (`acquire_mcp_context`).

## 2. Core Domain (Value Proposition)
The core capability is the **Harness Lifecycle**: The autonomous transformation of an existing codebase into a structured, agentic-ready workspace with verified tools and domain-aware prompts.

## 3. Aggregates & Invariants (Transactional Boundaries)
*   **Minting Transaction**: A Workspace must only be minted if Discovery has successfully categorized the tech stack and proposed a valid SME configuration.
*   **Agent Identity**: An Agent's system prompt must always include the `CodeGraph` MCP and local skill mandates to ensure operational consistency.

## 4. Domain Events & Coordination (Asynchrony)
*   **DiscoveryCompleted**: Triggers the Minting Engine to present `ONBOARDING_DOMAIN.md` to the user.
*   **MintingFinalized**: Signals that the Workspace is ready for active development.

## 5. Context Mapping (Contract Ownership)
*   **CodeGraph MCP**: The Harness is a **Conformist** to the `CodeGraph` protocol for codebase analysis.
*   **Boilerplate Template**: The Minting Engine treats the Boilerplate as an **Upstream/Supplier**.

## Key Relationships
*   A **Harness** uses a **Discovery Engine** to analyze a codebase.
*   A **Minting Engine** uses outputs from Discovery and a **Boilerplate Template** to generate a **Workspace**.
*   A **Workspace** contains **Agents** (Markdown) and centralized Orchestration Rules.
*   **Agents** invoke **Skills** during execution phases.