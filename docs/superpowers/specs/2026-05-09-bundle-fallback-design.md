# Bundle Fallback and Generation Design

## Objective
Update `harness-wf init` to correctly resolve the `--bundle` path and provide a fallback mechanism to generate the `.codegraph` wiki if no valid context is found in either the provided bundle or the target project directory.

## Core Changes

### 1. `cli.py`: Fast Path Existence Check & Generation Prompt
Before invoking the heavy discovery engine, we will perform a quick check for the index database.

*   **Resolution:**
    *   If `--bundle <path>` is provided, resolve it as an absolute path relative to the user's current working directory (where they ran the command).
    *   Define the target paths to check:
        1.  The resolved bundle path (if provided).
        2.  `os.path.join(args.project_path, ".codegraph")`
*   **Existence Check:**
    *   Check if either path exists and contains a `wiki` subdirectory or an `INDEX.md` file.
*   **Fallback Prompt:**
    *   If no index is found in either location, prompt the user: `No existing CodeGraph database found. Would you like to generate one now using 'CodeGraph wiki generate'? (Y/n):`
    *   If **Yes**:
        *   Execute `CodeGraph wiki generate` within `args.project_path`.
        *   **Crucial:** We must pass the collected API key to the subprocess based on the selected LLM provider (e.g., set `ANTHROPIC_API_KEY` in the environment if the user selected anthropic, or `OPENAI_API_KEY`, etc.) as the indexer requires it.
    *   If **No**:
        *   Proceed, but print a warning that context will be severely limited.

### 2. `discovery_engine.py`: Passing the Resolved Bundle
*   Update `acquire_mcp_context(project_path: str, bundle_path: str = None)`
*   If `bundle_path` is provided, prioritize reading `index.md` and `architecture.md` from the bundle's `wiki` folder.
*   If not found there, fallback to checking `<project_path>/.codegraph/wiki`.
*   If neither has the files, return a default "No codebase wiki found" string.

### 3. `minting_engine.py`: Consistent Resolution
*   Ensure the wiki migration logic in `mint_workspace` uses the *same* absolute path resolution logic for `bundle_override` as `cli.py` to ensure the correct folder is migrated.
