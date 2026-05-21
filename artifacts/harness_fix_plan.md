# Implementation Plan: Harness Architecture Fixes

**Objective**: Align the `harness` implementation with the `designs/harness/harness_init_architecture.md` document based on the findings in `artifacts/architecture_accuracy_report.md`.

## Tasks

1.  **Fix Dynamic Agent Discovery (`harness/cli.py`)**:
    *   Find where `selected_agents = []` is initialized.
    *   Update `cli.py` to actually call `discover_agents(context_str, ..., llm_provider=args.llm, api_key=api_key, model=args.model, ddd_context=final_ddd_context)` before calling `mint_workspace`. Note: You may need to handle the `feature_fetcher_yaml_path` argument, perhaps using a fallback or resolving it relative to the boilerplate.
    *   Ensure the discovered agents are appended or assigned to `selected_agents`.

2.  **Automate Setup Execution (`harness/cli.py`)**:
    *   At the end of the `main()` function, after minting and printing instructions, implement a `subprocess.run()` call to execute the generated `setup_harness.sh` script automatically.
    *   The path to the script will be based on the selected platform (e.g., `.gemini/scripts/setup_harness.sh`).
    *   Handle potential execution errors gracefully.

3.  **Implement JSON Retry Loop (`harness/discovery_engine.py`)**:
    *   In both `discover_agents` and `discover_ddd_context`, replace the single `try/except json.JSONDecodeError` block with a `while` loop that attempts to query the LLM and parse the JSON up to 3 times.
    *   If all 3 attempts fail, return the fallback default value and log an appropriate error message.

4.  **Sync Documentation (`designs/harness/harness_init_architecture.md`)**:
    *   Update the document to reflect that skills are stored in platform-specific directories (e.g., `.{platform}/skills/`) rather than `_agents/skills/`.
    *   Update the document to reflect the actual `CodeGraph serve` command arguments (e.g., adding `--all-tools`).

## Verification
*   Ensure all modifications pass existing tests (if any) or do not introduce syntax errors.
*   The `harness init` command should execute the full flow automatically without hanging on manual script execution (unless intended by platform specifics).