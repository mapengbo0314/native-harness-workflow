# Project Onboarding Domain

**Detected Tech Stack:** Python

Based on the codebase scan, I have identified **Analyzed Codebase Context** as a core complex domain. I propose creating a dedicated agent to protect this logic.

## Proposed Domain SME Agent

**Proposed Agent Name:** `@automation-strategist`
*(Edit the name above if incorrect. Must be lowercase.)*

## Deterministic DDD Alignment

### 1. Ubiquitous Language (Glossary)
*Key terms defined by business experts:*
*   **Automated Purpose**: The specific, measurable goal or outcome that an automated process is designed to achieve.
*   **Automated Vocab**: A standardized set of terms and definitions used to describe automation concepts, processes, and components within the organization.
*   **Automated Invariants**: Core, non-negotiable rules that govern the behavior and integrity of all automated systems and processes.
*   **Workflow Execution**: The successful completion of a defined sequence of automated tasks designed to achieve a specific objective.

### 2. Core Domain (Value Proposition)
*The single core capability that provides primary value:*
*   **Enabling seamless and intelligent automation across various business processes, leading to increased efficiency, reduced manual effort, and improved data accuracy.**

### 3. Aggregates & Invariants (Transactional Boundaries)
*Data that must absolutely always be updated together:*
1. All automated processes must adhere to predefined, validated business rules.
2. Data integrity must be maintained throughout all automation workflows.
3. Automation outputs must be traceable to their originating inputs and processes.
4. Unauthorized access or modification of automation configurations is strictly prohibited.

### 4. Domain Events & Coordination (Asynchrony)
*Significant actions that others need to know about:*
*   **Workflow Execution Started**
*   **Workflow Execution Completed Successfully**
*   **Workflow Execution Failed**

### 5. Context Mapping (Contract Ownership)
*Who dictates the shape of external data contracts:*
*   **This system provides core automation capabilities that can be leveraged by various other systems and domains within the organization. It acts as a central engine for process automation, receiving requests, executing workflows, and providing status updates.  Integration with other systems will likely occur via APIs or message queues to trigger or monitor automation tasks.  The 'fetch' MCP would be relevant for interacting with external APIs for data retrieval or process initiation.**

## Proposed Skills
*(Delete the line of any skill you do NOT want installed)*
- [x] orchestrator-plugin (local-plugin) <!-- type:skill -->
- [x] grill-with-docs (https://raw.githubusercontent.com/mattpocock/skills/main/skills/engineering/grill-with-docs/SKILL.md) <!-- type:skill -->

## Proposed MCP Tools
*(Delete the line of any MCP you do NOT want installed)*
- [x] fetch (npx -y @modelcontextprotocol/server-fetch)

*(When you have finished editing this file, return to the terminal and press ENTER to continue minting)*