# Harness Init Refactor Design

## Purpose
To fix the bugs in `harness-wf init` that cause `skills/` and `agents/` to not be generated for the Gemini platform, and to cleanly refactor the initialization process to eliminate Claude-specific hardcoding from the central CLI flow.

## 1. Fix the Positional Argument Bug
- **Issue:** The `mint_workspace` function gained a new `model_choice` argument, shifting the positional arguments. In `src/harness/init/cli.py`, `boilerplate_dir` is currently passed as a positional argument. As a result, it populates `model_choice` instead of `boilerplate_dir`, leaving `boilerplate_dir` as `None`. This causes `mint_workspace` to silently skip copying the boilerplate for non-Claude platforms.
- **Solution:** Change the `mint_workspace` call in `src/harness/init/cli.py` to pass `boilerplate_dir` as a named argument (`boilerplate_dir=str(boilerplate_dir)`).

## 2. Shared Functions Relocation
- **Issue:** `copy_runtime_modules` is located in `src/harness/init/plugin_generator.py` but is used globally across all platforms.
- **Solution:** Move `copy_runtime_modules` to `src/harness/init/minting_engine.py` (or a utility file) to prevent architectural cross-contamination.

## 3. Adapter-Driven Boilerplate Rearrangement
- **Issue:** Currently, `mint_workspace` copies all boilerplate to the harness root. For Claude, `generate_orchestrator_plugin` manually re-copies the payload files to `plugin-generated/`, and then `cli.py` executes a `shutil.rmtree` to delete the first copy. This is an anti-pattern and hardcodes platform logic in the generic `cli.py`.
- **Solution:**
  - Remove the hardcoded `if adapter.get_platform_name() == "claude":` block and redundant `shutil.rmtree` from `cli.py`.
  - Update `ClaudeAdapter.generate_core_infrastructure()` in `src/harness/adapters/claude.py` to move the payload directories (`skills`, `agents`, `hooks`, `scripts`, `pyproject.toml`) from the top level into the `plugin-generated/` folder.
  - Simplify `generate_orchestrator_plugin` to exclusively handle the generation of Claude-specific manifests (`plugin.json`, `hooks.json`, `README.md`) without copying boilerplate.

## 4. Spec Self-Review
- **Placeholder scan:** None found.
- **Internal consistency:** Yes, all three points align to correctly initialize a workspace based on platform via adapters.
- **Scope check:** Scope is tightly constrained to the initialization logic (`cli.py`, `minting_engine.py`, `plugin_generator.py`, `adapters/claude.py`).
- **Ambiguity check:** The paths and functions involved are explicitly named.
