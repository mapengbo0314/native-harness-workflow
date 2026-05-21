# Design Doc: Phased Onboarding & Domain SME Synthesis

**Status:** Draft
**Date:** 2026-05-10
**Topic:** Enhancing project onboarding with tech-stack-aware discovery and custom domain-expert agents.

## 1. Problem Statement
The current onboarding process in the Agentic Harness is either too generic (providing role-based agents like `@implementer`) or relies on LLM synthesis that lacks deterministic grounding in the project's unique architectural constraints. This leads to agents that don't "know" the project's deep business rules (the MOAT).

## 2. Proposed Solution
Implement a **Phased Onboarding Workflow** that uses an interactive "Handshake" document (`ONBOARDING_DOMAIN.md`) to capture domain intelligence. This intelligence is then used to synthesize exactly **one custom @domain-sme agent** that acts as the project's architectural guardian.

### 2.1 The Phased Workflow (Approach 2: Paused Loop)
1. **Discovery Phase**: The Harness scans the codebase using the `CodeGraph` MCP server.
2. **Drafting Phase**: It generates `ONBOARDING_DOMAIN.md` containing:
    * Detected Tech Stack.
    * Proposed Domain SME Agent (Name, Invariants, Glossary).
    * Questions for the user to fill in.
3. **The Pause**: The CLI pauses and waits for the user to edit the file and press ENTER.
4. **Minting Phase**: The Harness reads the completed file, synthesizes the custom agent via LLM, and writes the specialized workspace.

## 3. Component Details

### 3.1 `harness/discovery_engine.py` Enhancement
* **Tech Stack Detection**: Improved logic to parse `package.json`, `Cargo.toml`, etc., and summarize the architecture.
* **Risk/Domain Identification**: A specialized LLM prompt to identify the *single most complex or critical domain* in the project.
* **Template Generation**: Logic to write the initial `ONBOARDING_DOMAIN.md`.

### 3.2 `harness/minting_engine.py` Enhancement
* **Pause/Resume Logic**: Implement a simple terminal input wait.
* **SME Synthesis**: A new function `synthesize_domain_sme()` that takes the `ONBOARDING_DOMAIN.md` context and generates a rigid Markdown agent file.
* **Orchestrator Patching**: Logic to dynamically insert the new `@domain-sme` into the `orchestrator.md` and `dispatch_rules.md`.

### 3.3 The `@domain-sme` Agent Structure
* **Focus**: Invariants (rules that must not break) and Glossary (ubiquitous language).
* **Role**: Auditor and Consultant. It is forbidden from writing implementation code; it only reviews and rejects plans that violate the domain.

## 4. Design for Isolation & Clarity
* The `domain-sme` is isolated from the generic `implementer`.
* The `ONBOARDING_DOMAIN.md` acts as the single source of truth for the synthesis phase.

## 5. Success Criteria (Sphinch Marks)
* [ ] `harness` generates a valid `ONBOARDING_DOMAIN.md` after a scan.
* [ ] The CLI successfully pauses execution and waits for user confirmation.
* [ ] The minted `@domain-sme` agent contains the invariants added by the user in the doc.
* [ ] The `orchestrator.md` in the new workspace includes the `@domain-sme` in its routing instructions.

## 6. Alternatives Considered
* **Approach 1 (Two-Command CLI)**: Rejected for being less integrated, though technically safer regarding timeouts.
* **Multiple Domain Agents**: Rejected to prevent "Expert Bloat" and maintain high context efficiency.
