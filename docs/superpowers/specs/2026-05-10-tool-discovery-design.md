# Design Doc: Workspace-Level Skill & MCP Discovery

**Status:** Draft
**Date:** 2026-05-10
**Topic:** Automating the discovery and local installation of specialized Skills and MCP tools during project onboarding.

## 1. Problem Statement
Project onboarding currently provides a static set of boilerplate skills and one CodeGraph MCP. It does not automatically find and install specialized tools (like `pytest-patterns` or `postgres-mcp`) that are relevant to the project's specific tech stack and domain. Furthermore, tools are often managed globally rather than locally at the workspace level.

## 2. Proposed Solution
Enhance the **Discovery Engine** to search for and recommend Skills and MCP tools based on the detected tech stack. These recommendations will be presented to the user as editable checklists in the `ONBOARDING_DOMAIN.md` document. The **Minting Engine** will then handle the local installation (for skills) and ephemeral configuration (for MCPs) at the workspace level.

### 2.1 The Hybrid Discovery Flow
1. **Tool Discovery**: During the initial scan, the Harness uses a specialized LLM prompt ("The Tool Scout") to identify relevant Skills and MCP tools.
2. **Review Handshake**: Recommendations are written into `ONBOARDING_DOMAIN.md` as Markdown checklists.
3. **Local Installation**:
    *   **Skills**: Selected remote skills are downloaded into the workspace's `.gemini/skills/` directory.
    *   **MCPs**: Selected MCPs are added to the workspace's `mcp.json` using ephemeral execution commands (`npx`, `uvx`, etc.) to avoid global pollution.

## 3. Component Details

### 3.1 `harness/discovery_engine.py` Enhancement
*   **The Tool Scout**: New logic to query a "Knowledge Base" (or simulate a search) for Skills and MCPs that match the detected languages and frameworks.
*   **Template Injection**: Update `generate_onboarding_domain_doc` to include the `## Proposed Skills` and `## Proposed MCP Tools` sections with checklists.

### 3.2 `harness/minting_engine.py` Enhancement
*   **Skill Downloader**: New logic to parse the selected skill URLs from the handshake doc and download them into the local workspace.
*   **MCP Configurator**: New logic to generate the platform-specific `mcp.json` (Gemini, Claude, etc.) using `npx -y` or `uvx` for the selected tools.
*   **Workspace-Level Scoping**: Ensure all configurations (including the CodeGraph MCP) use local paths relative to the workspace root.

## 4. Platform Adaptation
*   **Gemini**: Writes to `.gemini/mcp.json` and `.gemini/skills.json`.
*   **Claude**: Writes to `.claude/mcp.json`.

## 5. Success Criteria (Sphinch Marks)
* [ ] `ONBOARDING_DOMAIN.md` contains a list of tech-stack-relevant Skills and MCPs.
* [ ] Deleting a tool from the checklist in the doc prevents it from being installed.
* [ ] Remote skills are downloaded into the workspace `.gemini/skills/` folder.
* [ ] The generated `mcp.json` uses `npx` or `uvx` for newly added tools.

## 6. Alternatives Considered
*   **Local Directory for MCPs**: Rejected to avoid the complexity of managing local `node_modules` or `venvs` inside the harness folder.
*   **Global Installation**: Rejected to maintain workspace isolation.
