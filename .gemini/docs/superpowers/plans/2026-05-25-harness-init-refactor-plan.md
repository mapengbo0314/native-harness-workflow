# Harness Init Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the harness initialization to fix Gemini generation bugs by addressing positional arguments, relocating shared functions, and letting adapters handle platform-specific boilerplate rearrangement. Includes end-to-end headless testing.

**Architecture:**
- `cli.py` will correctly pass keyword arguments to `mint_workspace`.
- `cli.py` will no longer hold Claude-specific cleanup logic.
- `copy_runtime_modules` moves to `minting_engine.py`.
- `ClaudeAdapter` handles the structural rearrangement of files into `plugin-generated/` during `generate_core_infrastructure`.
- `plugin_generator.py` focuses purely on manifesting the Claude config.

**Tech Stack:** Python 3, `pytest` for integration testing.

---

### Task 1: Fix Positional Arguments in cli.py

**Files:**
- Modify: `src/harness/init/cli.py`

- [ ] **Step 1: Write the failing test**
(We'll test this holistically in Task 4, but we can verify the fix directly first).
We skip unit testing this one-line fix in favor of the integration test in Task 4.

- [ ] **Step 2: Write minimal implementation**
Modify `src/harness/init/cli.py` where `mint_workspace` is called.

```python
        # We pass the bundled boilerplate_dir and target the temp directory
        mint_workspace(
            str(temp_harness_dir), 
            selected_agents, 
            args.project_path, 
            platform_choice, 
            boilerplate_dir=str(boilerplate_dir), 
            logical_harness_name=harness_folder
        )
```

- [ ] **Step 3: Commit**

```bash
git add src/harness/init/cli.py
git commit -m "fix(init): pass boilerplate_dir as kwargs to mint_workspace"
```

---

### Task 2: Relocate copy_runtime_modules

**Files:**
- Modify: `src/harness/init/plugin_generator.py`
- Modify: `src/harness/init/minting_engine.py`
- Modify: `src/harness/init/cli.py`

- [ ] **Step 1: Move function definition**
Cut `copy_runtime_modules` from `src/harness/init/plugin_generator.py` and paste it into `src/harness/init/minting_engine.py`.

```python
def copy_runtime_modules(target_dir: Path):
    """Copies runtime dispatcher and discovery_engine to the harness environment."""
    runtime_src = Path(__file__).parent.parent / "runtime"
    
    # Ensure src directory exists inside the harness plugin payload
    src_dir = target_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy dispatcher
    dispatcher_src = runtime_src / "dispatcher.py"
    if dispatcher_src.exists():
        print(f"[HARNESS] Copying dispatcher.py...")
        shutil.copy2(dispatcher_src, src_dir / "dispatcher.py")
        
    # Copy llm client
    llm_client_src = runtime_src / "llm_client.py"
    if llm_client_src.exists():
        print(f"[HARNESS] Copying llm_client.py...")
        shutil.copy2(llm_client_src, src_dir / "llm_client.py")
        
    # Copy discovery engine 
    # (Discovery engine lives in init, not runtime, but is needed at runtime)
    discovery_src = Path(__file__).parent / "discovery_engine.py"
    if discovery_src.exists():
        print(f"[HARNESS] Copying discovery_engine.py...")
        shutil.copy2(discovery_src, src_dir / "discovery_engine.py")
```

- [ ] **Step 2: Update imports in `cli.py`**
In `src/harness/init/cli.py`, change:
```python
        # Copy runtime modules for ALL platforms (so hooks can load them locally)
        from harness.init.plugin_generator import copy_runtime_modules
        copy_runtime_modules(temp_harness_dir)
```
To:
```python
        # Copy runtime modules for ALL platforms (so hooks can load them locally)
        from harness.init.minting_engine import copy_runtime_modules
        copy_runtime_modules(temp_harness_dir)
```

- [ ] **Step 3: Update imports in `plugin_generator.py`**
If `copy_runtime_modules` is used inside `plugin_generator.py`, import it from `minting_engine`:
```python
from harness.init.minting_engine import copy_runtime_modules
```

- [ ] **Step 4: Commit**

```bash
git add src/harness/init/cli.py src/harness/init/plugin_generator.py src/harness/init/minting_engine.py
git commit -m "refactor(init): move copy_runtime_modules to minting_engine"
```

---

### Task 3: Refactor Boilerplate Rearrangement (Claude Adapter & cli.py cleanup)

**Files:**
- Modify: `src/harness/adapters/claude.py`
- Modify: `src/harness/init/cli.py`
- Modify: `src/harness/init/plugin_generator.py`

- [ ] **Step 1: Update ClaudeAdapter to handle rearrangement**
In `src/harness/adapters/claude.py`, implement `generate_core_infrastructure`:

```python
    def generate_core_infrastructure(self, project_path: Path) -> None:
        import shutil
        harness_dir = project_path / ".harness_tmp"
        if not harness_dir.exists():
            harness_dir = project_path / self.get_config_dir_name()
            
        plugin_dir = harness_dir / "plugin-generated"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # Move payload directories into plugin-generated
        payload_dirs = ["skills", "agents", "hooks", "scripts", "src"]
        payload_files = ["pyproject.toml"]
        
        for p_dir in payload_dirs:
            src_path = harness_dir / p_dir
            if src_path.exists():
                dest_path = plugin_dir / p_dir
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.move(str(src_path), str(dest_path))
                
        for p_file in payload_files:
            src_path = harness_dir / p_file
            if src_path.exists():
                shutil.move(str(src_path), str(plugin_dir / p_file))
```

- [ ] **Step 2: Clean up `cli.py`**
In `src/harness/init/cli.py`, remove the Claude-specific cleanup block.

Delete this entire block:
```python
                # Post-generation cleanup: remove boilerplate agents and skills
                # as they are now inside the plugin
                harness_path = temp_harness_dir
                
                # Clean agents folder
                agents_dir = harness_path / "agents"
                if agents_dir.exists():
                    shutil.rmtree(agents_dir)
                                
                # Clean skills folder
                skills_dir = harness_path / "skills"
                if skills_dir.exists():
                    shutil.rmtree(skills_dir)
                    
                print("[HARNESS] Cleaned up redundant top-level boilerplate folders for plugin.")
```

- [ ] **Step 3: Simplify `generate_orchestrator_plugin`**
In `src/harness/init/plugin_generator.py`, update `generate_orchestrator_plugin` to NOT call `copy_static_plugin_assets` and NOT copy agents, because `generate_core_infrastructure` has already moved the populated files into place.

Remove:
```python
        # Copy canonical static plugin payload.
        copy_static_plugin_assets(plugin_dir, bp_dir, fallback_bp_dir)
        remove_obsolete_generated_files(plugin_dir)
```
And remove:
```python
        # Copy boilerplate agents first
        agents_src = bp_dir / "agents"
        if agents_src.exists():
            print(f"[HARNESS] Copying boilerplate agents from {agents_src}...")
            shutil.copytree(agents_src, plugin_dir / "agents", dirs_exist_ok=True, ignore=COPY_IGNORE)
            
        # Copy dynamically generated agents from harness temp dir
        harness_agents = harness_dir / "agents"
        if harness_agents.exists():
            print(f"[HARNESS] Copying dynamically generated agents from {harness_agents}...")
            shutil.copytree(harness_agents, plugin_dir / "agents", dirs_exist_ok=True, ignore=COPY_IGNORE)
```
And remove:
```python
        print(f"[HARNESS] Copying runtime modules...")
        copy_runtime_modules(plugin_dir)
```

- [ ] **Step 4: Commit**

```bash
git add src/harness/adapters/claude.py src/harness/init/cli.py src/harness/init/plugin_generator.py
git commit -m "refactor(init): adapter-driven boilerplate rearrangement"
```

---

### Task 4: Headless Integration Tests

**Files:**
- Create: `tests/integration/test_headless_generation.py`

- [ ] **Step 1: Write the integration test**

```python
import os
import shutil
import tempfile
import subprocess
from pathlib import Path

def test_headless_harness_generation():
    platforms = {
        "1": ".gemini",
        "2": ".claude",
        "3": ".cursor",
        "4": ".agents",
        "5": ".codex"
    }

    cli_script = Path(__file__).parent.parent.parent / "src" / "harness" / "init" / "cli.py"

    for choice, target_dir_name in platforms.items():
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                env = os.environ.copy()
                env["HARNESS_HEADLESS"] = "1"
                env["HARNESS_PLATFORM"] = choice

                # Mock .codegraph to bypass npm installation
                (Path(tmpdir) / ".codegraph").mkdir()
                (Path(tmpdir) / ".codegraph" / "codegraph.db").touch()

                result = subprocess.run(
                    ["python3", str(cli_script), "init", "--project-path", tmpdir],
                    env=env,
                    capture_output=True,
                    text=True
                )

                assert result.returncode == 0, f"Platform {choice} failed: {result.stderr}"
                
                target_path = Path(tmpdir) / target_dir_name
                assert target_path.exists(), f"Target dir {target_dir_name} not found for platform {choice}"

                # Validate expected payload directories based on platform
                if choice == "2":  # Claude
                    payload_base = target_path / "plugin-generated"
                else:
                    payload_base = target_path

                assert (payload_base / "skills").exists(), f"skills/ not found in {payload_base} for platform {choice}"
                assert (payload_base / "agents").exists(), f"agents/ not found in {payload_base} for platform {choice}"
                assert (target_path / "AGENTS.md").exists(), f"AGENTS.md not found in {target_path} for platform {choice}"
                assert (target_path / "orchestrator.md").exists(), f"orchestrator.md not found in {target_path} for platform {choice}"

            finally:
                # The tempfile.TemporaryDirectory cleans up stragglers automatically
                pass
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/integration/test_headless_generation.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_headless_generation.py
git commit -m "test(init): add headless integration testing for all platforms"
```
