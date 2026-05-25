# Strip State and Configs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip away the generation of state, configurations (`mcp.json`, `.mcp.json`, `strategy.json`), and `contracts` during harness minting to simplify the boilerplate.

**Architecture:** We will modify the core minting and CLI logic to bypass the creation and copying of these assets, and update the associated tests (e2e, integration, and unit tests) to expect their absence.

**Tech Stack:** Python, pytest

---

### Task 1: Update CLI configuration generation logic and tests

**Files:**
- Modify: `tests/e2e/test_full_harness_lifecycle.py`
- Modify: `tests/integration/test_platform_snapshots.py`
- Modify: `src/harness/cli.py`

- [ ] **Step 1: Update failing tests for repo MCP config**

Modify `tests/e2e/test_full_harness_lifecycle.py` (around line 101). Change the assertion to check that `.mcp.json` is NOT created:

```python
        # Remove or invert the assertion
        assert not (project_path / ".mcp.json").exists(), ".mcp.json should not be generated"
```

Modify `tests/integration/test_platform_snapshots.py`. Find assertions for `.mcp.json` (e.g., `assert (temp_project / ".mcp.json").exists()`) and change them to `assert not ...exists()`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/e2e/test_full_harness_lifecycle.py tests/integration/test_platform_snapshots.py -v`
Expected: FAIL because `.mcp.json` is currently still being generated.

- [ ] **Step 3: Modify implementation**

In `src/harness/cli.py`, locate `run_embedded_setup`.
Comment out or remove the call to `_write_repo_mcp_config(project_path, mcps_to_install)`.

```python
    if sys.version_info < (3, 8):
        raise HarnessSetupError("Python 3.8+ is required.")

    # _write_repo_mcp_config(project_path, mcps_to_install)

    adapter = get_adapter(_platform_name(platform_choice))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/e2e/test_full_harness_lifecycle.py tests/integration/test_platform_snapshots.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/cli.py tests/e2e/test_full_harness_lifecycle.py tests/integration/test_platform_snapshots.py
git commit -m "feat: disable repo-level .mcp.json generation"
```

### Task 2: Update Minting Engine tests for strategy and mcp config

**Files:**
- Modify: `tests/unit/test_minting_engine.py`
- Modify: `tests/e2e/test_transactional_minting.py`
- Modify: `src/harness/minting_engine.py`

- [ ] **Step 1: Update failing tests for strategy.json and mcp.json**

In `tests/unit/test_minting_engine.py`, update `test_mint_workspace_persists_strategy` and `test_mint_workspace_uses_provided_tech_stack` to assert that `strategy.json` does NOT exist:

```python
        strategy_path = target_dir / "strategy.json"
        assert not strategy_path.exists(), f"strategy.json should NOT exist at {strategy_path}"
        
        # Remove the code that tries to open and read strategy.json
```

In `tests/e2e/test_transactional_minting.py` (around line 50 and 95), remove or invert assertions regarding `mcp.json`. Since the test explicitly tests deep merging of `mcp.json`, you may need to comment out or skip the sections testing `mcp.json` modification.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_minting_engine.py tests/e2e/test_transactional_minting.py -v`
Expected: FAIL because the files are still being generated or expected.

- [ ] **Step 3: Modify implementation**

In `src/harness/minting_engine.py`, locate `ignore_patterns` function inside `mint_workspace` (around line 150):

```python
    def ignore_patterns(dir_path, contents):
        ignored = ['.git', '__pycache__', '.DS_Store', 'contracts', 'state']
        return [i for i in contents if i in ignored or i.endswith('.log')]
```

In `src/harness/minting_engine.py`, comment out the `mcp.json` generation:

```python
    # Generate mcp.json as a fallback/reference configuration
    # mcp_path = target_path / "mcp.json"
    # with open(mcp_path, 'w') as f:
    #      json.dump(mcp_config, f, indent=2)
```

In `src/harness/minting_engine.py`, update `_persist_verification_strategy` to bypass writing:

```python
        if tech_stack_data and "strategy" in tech_stack_data:
            # strategy_path = target_path / "strategy.json"
            # with open(strategy_path, "w") as f:
            #     json.dump(tech_stack_data["strategy"], f, indent=2)
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_minting_engine.py tests/e2e/test_transactional_minting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/harness/minting_engine.py tests/unit/test_minting_engine.py tests/e2e/test_transactional_minting.py
git commit -m "feat: disable strategy.json, mcp.json, state, and contracts generation"
```

### Task 3: Verify Test Suite

**Files:**
- N/A

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`

- [ ] **Step 2: Fix any remaining snapshot issues**

If snapshot tests in `tests/integration/test_platform_snapshots.py` fail because they expect `mcp.json` or `strategy.json` in the generated folder structure, update the test expectations to remove those files from the expected output lists (e.g., around line 143).

- [ ] **Step 3: Commit**

```bash
git commit -am "test: fix remaining snapshot tests for stripped configs"
```

### Task 4: Clean up `src/harness` source files and boilerplate

**Files:**
- Modify: `src/harness/plugin_generator.py`
- Modify: `src/harness/cli.py`
- Delete: `src/harness/templates/boilerplate/contracts` directory

- [ ] **Step 1: Remove `contracts` from `plugin_generator.py`**

In `src/harness/plugin_generator.py` (around line 226), remove `"contracts"` from the list of directories to copy:

```python
    for name in ["skills", "scripts", "hooks"]:
```

- [ ] **Step 2: Remove `_write_setup_state` from `cli.py`**

In `src/harness/cli.py`, completely remove the `_write_setup_state` function definition since it's no longer used and generates state files we don't want.

- [ ] **Step 3: Delete boilerplate `contracts` directory using git**

Run:
```bash
git rm -r src/harness/templates/boilerplate/contracts
```

- [ ] **Step 4: Update `verify_contract.py`**

If `src/harness/templates/boilerplate/scripts/verify_contract.py` exists, we may either want to delete it or remove the parts verifying contracts since contracts are gone. For this step, simply delete the verification script as well:

```bash
git rm src/harness/templates/boilerplate/scripts/verify_contract.py
```
*(If the script doesn't exist or git rm fails, just move on)*

- [ ] **Step 5: Commit**

```bash
git commit -am "refactor: purge state, configs, and contracts from boilerplate and plugin generator"
```
