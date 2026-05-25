# Project Onboarding Domain

**Detected Tech Stack:** Python

Based on the codebase scan, I have identified **Analyzed Codebase Context** as a core complex domain. I propose creating a dedicated agent to protect this logic.

## Proposed Domain SME Agent

**Proposed Agent Name:** `@workflow-architect`
*(Edit the name above if incorrect. Must be lowercase.)*

## Deterministic DDD Alignment

### 1. Ubiquitous Language (Glossary)
*Key terms defined by business experts:*
*   **Harness**: The execution environment responsible for managing and running distributed tasks within the workflow.
*   **Workflow (wf)**: A defined sequence of tasks orchestrated by the engine.
*   **Phase**: A distinct stage within the project's development or testing lifecycle.
*   **DAC (Design as Code)**: The principle of defining and managing design elements and workflow logic through code, enabling version control and automation.

### 2. Core Domain (Value Proposition)
*The single core capability that provides primary value:*
*   **Enables robust, code-driven orchestration of distributed tasks with clear visibility into phased development and artifact generation, fostering a 'design as code' paradigm for enhanced automation and traceability.**

### 3. Aggregates & Invariants (Transactional Boundaries)
*Data that must absolutely always be updated together:*
1. All task execution must occur within a defined Harness.
2. Workflow definitions must be versioned and managed as code (DAC).
3. The system must maintain accurate tracking of distinct development/testing Phases.
4. Generated Artifacts are immutable once created and represent a verifiable output of a phase or task.

### 4. Domain Events & Coordination (Asynchrony)
*Significant actions that others need to know about:*
*   **WorkflowExecutionStarted**
*   **PhaseCompleted**

### 5. Context Mapping (Contract Ownership)
*Who dictates the shape of external data contracts:*
*   **This Workflow Orchestration Engine acts as a core backend service. It might integrate with frontend systems for user interface display of workflows and artifacts, and with external CI/CD pipelines for task execution. It relies on version control systems for DAC and potentially cloud-based services for distributed task execution.**

## Proposed Skills
*(Delete the line of any skill you do NOT want installed)*
- [x] grill-with-docs (https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/grill-with-docs/SKILL.md) <!-- type:skill -->

## Proposed MCP Tools
*(Delete the line of any MCP you do NOT want installed)*
- [x] orchestrator-plugin (local-plugin)
- [x] git-mcp (npx -y @mseep/git-mcp-server)

*(When you have finished editing this file, return to the terminal and press ENTER to continue minting)*