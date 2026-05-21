# Architecture Accuracy Report: Harness Init

**Document Evaluated**: `designs/harness/harness_init_architecture.md`
**Evaluation Date**: 2026-05-12
**Status**: ⚠️ SIGNIFICANT DISCREPANCIES FOUND

## Executive Summary

While the foundational engine logic exists in `harness/discovery_engine.py` and `harness/minting_engine.py`, the core orchestration in `harness/cli.py` fails to fulfill the "Dynamic Agent Discovery" and "One-Click Execution" promises made in the design document. Most notably, the code that discovers specialized agents is never actually invoked, and the automated setup script requires manual user execution.

## Key Discrepancies

### 1. Orchestration Failure (Dynamic Discovery)
*   **Document Claim**: The CLI entry coordinates the sequential invocation of Context, Discovery, and Minting engines. `discover_agents` is updated to ground generated agents in DDD context.
*   **Actual State**: `harness/cli.py` initializes `selected_agents = []` and **never calls `discover_agents`**. As a result, no specialized agents are generated or passed to the `mint_workspace` function. The "grounded discovery" feature is dead code.

### 2. Manual vs. Automatic Execution
*   **Document Claim**: "The `setup_harness.sh` script is automatically executed by the CLI entry script upon successful minting."
*   **Actual State**: The CLI simply prints a "Next Steps" message instructions the user to run the script manually. No `subprocess.run` call exists for the setup script.

### 3. Missing Robustness Features (JSON Retries)
*   **Document Claim**: "Validation: It utilizes strict JSON schema validation loops with a 3-retry minimum to guarantee valid outputs."
*   **Actual State**: Both `discover_agents` and `discover_ddd_context` in `harness/discovery_engine.py` use a single `try/except` block for JSON parsing. There is **no retry logic** implemented.

### 4. Component Divergence
*   **CodeGraph Arguments**: 
    *   *Claim*: `CodeGraph serve --watch --wiki-auto-update`
    *   *Code*: `CodeGraph serve --watch --wiki-auto-update --all-tools` (Minor discrepancy, but adds unmentioned flags).
*   **Skill Paths**:
    *   *Claim*: `_agents/skills/`
    *   *Code*: `.{platform}/skills/` (e.g., `.gemini/skills/`).

## Verified Accurate Claims

*   ✅ **Context Engine Boundaries**: `acquire_mcp_context` correctly restricts reading to `index.md` and `architecture.md`.
*   ✅ **DDD Alignment Grill**: The interactive grill sequence in `cli.py` using `run_ddd_grill` is correctly implemented.
*   ✅ **Root Rule Placement**: Platform rule files (`GEMINI.md`, `CLAUDE.md`, etc.) are correctly generated in the project root.
*   ✅ **SME Agent Synthesis**: The deterministic synthesis of a Domain SME agent from the `ONBOARDING_DOMAIN.md` doc is functional.

## Recommendations

1.  **Integrate `discover_agents`**: Update `harness/cli.py` to actually call `discover_agents` and populate `selected_agents` before calling `mint_workspace`.
2.  **Automate Setup**: Implement `subprocess.run` in `harness/cli.py` to execute the generated `setup_harness.sh` automatically.
3.  **Implement Retries**: Add the promised 3-retry loop to LLM query functions in `harness/discovery_engine.py`.
4.  **Sync Documentation**: Update `harness_init_architecture.md` to reflect the actual paths (e.g., `.{platform}/skills/`) or update the code to match the design.
