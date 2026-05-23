# Design Spec: Transactional Smart Merge for Safe Minting

**Date**: 2026-05-23  
**Status**: Draft  
**Topic**: Safe Minting and Harness Integrity  

## 1. Problem Statement
The current minting process (`harness init`) either overwrites existing files blindly or provides a vague warning. This risks destroying custom configurations (specialized agents, modified rules, manual skill entries) or creating "Frankenstein" states where old and new boilerplate are inconsistently mixed.

## 2. Proposed Solution: Transactional Smart Merge
We will implement a multi-stage minting process that treats the harness directory as a managed asset. Smart merging is the **default behavior**.

### 2.1 Strategy: The Atomic Swap
1. **Stage in `.harness_tmp`**: All boilerplate rendering and template processing happen in a temporary directory.
2. **Deterministic Merging**: 
    *   **Markdown (.md)**: Section-based replacement. We identify sections by headers (H1-H6). If a section in the new boilerplate matches an existing header, the content is updated (preserving existing sections not in boilerplate).
    *   **JSON/YAML**: Recursive deep merge. Arrays (like `skills` or `agents`) are unioned to avoid duplicates.
    *   **Code (.py, .sh, .js)**: If the file exists and is identical to the target boilerplate, it's ignored. 
3. **Conflict Resolution**: If a code file or structured file has a non-trivial conflict (e.g., incompatible schema or different code logic), the user is prompted to `[O]verwrite` or `[S]kip`.
4. **Finalization**: If successful, the existing `.gemini` (or equivalent) is backed up to `.gemini.old` and the temporary directory is moved to the target path.

### 2.2 Headless Support
In `HARNESS_HEADLESS=1` mode:
*   Conflicts are automatically resolved by preferring the **new boilerplate** (Overwrite) to ensure the harness remains functional with the latest tools.
*   A summary of merged/overwritten files is printed to stdout.

### 2.3 Error Handling & Atomicity
*   Any failure during the rendering or merging phase halts the process.
*   The original harness is never touched until the temporary directory is fully prepared and validated.

## 3. Component Impacts

### 3.1 `src/harness/minting_engine.py`
*   Refactor `mint_workspace` to take a `merge_strategy` parameter.
*   Implement `merge_markdown(existing_path, new_path)` using a header-based parser.
*   Implement `merge_structured(existing_path, new_path)` for JSON/YAML.

### 3.2 `src/harness/cli.py`
*   Add a check for `target_dir.exists()` before calling `mint_workspace`.
*   Implement the interactive prompt using `ask_user` or standard input.

## 4. Testing Strategy
*   **Unit Tests**: Mock existing harness directories with varied content and verify the result of `merge_markdown` and `merge_structured`.
*   **Integration Tests**: Run `init` on a directory with an existing `.gemini` and verify the "Atomic Swap" behavior.
