# Design: Deterministic Verification & High-Fidelity Discovery

**Date:** 2026-05-23  
**Status:** Approved  
**Topic:** Improving Harness onboarding accuracy and verification reliability.

## 1. Problem Statement
The current Agentic Harness relies on simple file-marker heuristics (e.g., checking for `package.json`) to guess the tech stack. This leads to:
1.  **Low Fidelity:** Failure to detect specific test runners (Playwright, Pytest, Vitest).
2.  **Missing Verification:** The Orchestrator often skips the `@verifier` agent because it lacks a deterministic "contract" on how to verify changes.
3.  **Inconsistent E2E:** No clear distinction between fast unit tests and slow, high-confidence E2E tests.

## 2. Proposed Solution

### 2.1 Deep Audit Discovery
Upgrade the onboarding engine to perform a symbol-based audit using CodeGraph.
*   **Symbol Detection:** Search for markers like `playwright.test`, `pytest.fixture`, `Component.tsx`, etc.
*   **Categorization:** Map findings to **Verification Profiles** (e.g., `web-frontend`, `python-api`).
*   **Path Awareness:** Support monorepos by mapping specific sub-directories to relevant test runners.

### 2.2 The Verification Strategy (`.harness/strategy.json`)
Decouple infrastructure/testing commands from domain logic (`ddd_context.json`).
*   **File Path:** `.harness/strategy.json`
*   **Structure:**
    ```json
    {
      "profiles": {
        "frontend": {
          "path": "src/ui",
          "stages": [
            { "name": "unit", "command": "npm run test:unit", "critical": true },
            { "name": "e2e", "command": "npx playwright test", "critical": false }
          ]
        }
      }
    }
    ```
*   **Enforcement Levels:** 
    *   **Unit:** Always mandatory for code changes.
    *   **E2E:** Mandatory for high-complexity tasks (features/bugfixes); optional/skippable for low-complexity tasks (typos/docs).

### 2.3 Deterministic Orchestration Gate
Update the `using-harness-superpowers` flow and Orchestrator mandates:
1.  **Mandatory Strategy Read:** The Orchestrator MUST read `.harness/strategy.json` during its initialization.
2.  **Verification Loopback:** The "Success" state requires a `QA_REPORT.md` from `@verifier` with a `PASS` status.
3.  **Autonomous Recovery:** If `@verifier` fails, the Orchestrator must analyze the failure and re-route to `@implementer` (code fix) or `@planner` (strategy fix) before asking the user for help.

### 2.4 User Experience
*   **Warning System:** If no tests are found, the user is warned in `ONBOARDING_GUIDE.md`.
*   **Reviewable Commands:** Discovered commands are placed in the onboarding documentation for user approval before being locked into the strategy.

## 3. Success Criteria
*   The Orchestrator correctly identifies and executes Playwright tests for a web feature.
*   The Orchestrator provides a failure analysis and re-routes to the implementer when a test fails.
*   The domain context (`ddd_context.json`) remains focused on logic, not test commands.
