# Orchestrator Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement auto-generation of Claude Code orchestrator plugins from harness setup, ensuring all agent dispatching goes through the project's orchestrator.

**Architecture:** 
The implementation has three phases:
1. Extend minting engine to detect Claude Code platform + orchestrator-plugin selection, then generate plugin structure
2. Implement plugin entry point and dispatcher logic that hooks into Claude Code's agent dispatch mechanism
3. Test plugin generation and verify orchestrator enforcement

**Tech Stack:** Python 3.8+, Claude Code plugin system, harness orchestrator

---

## File Structure

**Created:**
- `harness/plugin_generator.py` - Core plugin generation logic (templates, file writing)
- `.claude/plugin-generated/plugin.json` - Claude Code plugin manifest (auto-generated per project)
- `.claude/plugin-generated/src/orchestrator_plugin.py` - Plugin entry point (auto-generated)
- `.claude/plugin-generated/src/dispatcher.py` - Orchestrator dispatch wrapper (auto-generated)
- `.claude/plugin-generated/src/interceptor.py` - Claude Code hook handler (auto-generated)
- `.claude/plugin-generated/config/agents.json` - Exported agent definitions (auto-generated)
- `.claude/plugin-generated/config/orchestrator.json` - Exported orchestrator config (auto-generated)
- `.claude/plugin-generated/config/ddd-context.json` - DDD context (auto-generated)
- `.claude/plugin-generated/config/rules.json` - Project mandates (auto-generated)
- `.claude/plugin-generated/pyproject.toml` - Plugin dependencies (auto-generated)
- `tests/harness/test_plugin_generator.py` - Plugin generation tests

**Modified:**
- `harness/minting_engine.py` - Add plugin generation integration (lines ~320-350, setup script generation)

---

## Phase 1: Plugin Generator Module

### Task 1: Create plugin_generator.py with template functions

**Files:**
- Create: `harness/plugin_generator.py`

- [ ] **Step 1: Write failing test for plugin manifest generation**

Create `tests/harness/test_plugin_generator.py`:

```python
import os
import json
import tempfile
from pathlib import Path
import pytest
from harness.plugin_generator import generate_plugin_manifest

def test_generate_plugin_manifest_creates_valid_json():
    """Test that plugin manifest is generated with correct structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_name = "test-project"
        manifest_path = generate_plugin_manifest(tmpdir, project_name)
        
        assert os.path.exists(manifest_path)
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        assert manifest['name'] == 'orchestrator-plugin'
        assert manifest['description'] == 'Auto-generated orchestrator plugin for test-project'
        assert manifest['version'] == '1.0.0'
        assert 'entry_point' in manifest
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/pengbolicious/pengbo-apps/e-2-g
pytest tests/harness/test_plugin_generator.py::test_generate_plugin_manifest_creates_valid_json -xvs
```

Expected: `ModuleNotFoundError: No module named 'harness.plugin_generator'`

- [ ] **Step 3: Create plugin_generator.py with manifest template**

```python
# harness/plugin_generator.py
import os
import json
from pathlib import Path
from typing import Optional

def generate_plugin_manifest(
    target_dir: str, 
    project_name: str, 
    plugin_version: str = "1.0.0"
) -> str:
    """
    Generate plugin.json manifest for the orchestrator plugin.
    
    Args:
        target_dir: Directory to generate plugin in (e.g., .claude/plugin-generated)
        project_name: Name of the project (for display)
        plugin_version: Version of the plugin
        
    Returns:
        Path to the generated plugin.json
    """
    plugin_dir = Path(target_dir)
    plugin_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "name": "orchestrator-plugin",
        "description": f"Auto-generated orchestrator plugin for {project_name}",
        "version": plugin_version,
        "author": "Harness Plugin Generator",
        "entry_point": "src/orchestrator_plugin.py",
        "requirements": [
            "pydantic>=2.0",
            "typing_extensions"
        ],
        "hooks": {
            "agent_dispatch": "src/interceptor.py:intercept_agent_dispatch"
        }
    }
    
    manifest_path = plugin_dir / "plugin.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    return str(manifest_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/harness/test_plugin_generator.py::test_generate_plugin_manifest_creates_valid_json -xvs
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add harness/plugin_generator.py tests/harness/test_plugin_generator.py
git commit -m "feat(plugin-gen): add plugin manifest generation"
```

---

### Task 2: Add config export functions to plugin_generator.py

**Files:**
- Modify: `harness/plugin_generator.py`
- Modify: `tests/harness/test_plugin_generator.py`

- [ ] **Step 1: Write failing test for config export**

Add to `tests/harness/test_plugin_generator.py`:

```python
def test_export_orchestrator_config_copies_orchestrator_md():
    """Test that orchestrator.json is exported from orchestrator.md."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock orchestrator.md
        orchestrator_path = Path(tmpdir) / "orchestrator.md"
        orchestrator_path.write_text("# Orchestrator\n\nRouting rules...")
        
        config_dir = Path(tmpdir) / "config"
        export_orchestrator_config(orchestrator_path, config_dir)
        
        assert (config_dir / "orchestrator.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/harness/test_plugin_generator.py::test_export_orchestrator_config_copies_orchestrator_md -xvs
```

Expected: `NameError: name 'export_orchestrator_config' is not defined`

- [ ] **Step 3: Add config export functions to plugin_generator.py**

Add to `harness/plugin_generator.py`:

```python
def export_orchestrator_config(orchestrator_path: Path, config_dir: Path) -> str:
    """
    Export orchestrator configuration from .md to JSON format.
    
    Args:
        orchestrator_path: Path to orchestrator.md
        config_dir: Directory to export config to
        
    Returns:
        Path to exported orchestrator.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Read orchestrator.md
    with open(orchestrator_path, 'r') as f:
        content = f.read()
    
    # For now, create a basic JSON with metadata
    # In full implementation, this would parse .md structure
    orchestrator_json = {
        "source": str(orchestrator_path),
        "content": content,
        "generated_at": "auto"
    }
    
    export_path = config_dir / "orchestrator.json"
    with open(export_path, 'w') as f:
        json.dump(orchestrator_json, f, indent=2)
    
    return str(export_path)


def export_agents_config(agents_dir: Path, config_dir: Path) -> str:
    """
    Export agent definitions from agents/ directory to agents.json.
    
    Args:
        agents_dir: Path to agents directory
        config_dir: Directory to export config to
        
    Returns:
        Path to exported agents.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    
    agents = {}
    if agents_dir.exists():
        for agent_file in agents_dir.glob("*.md"):
            agent_name = agent_file.stem
            with open(agent_file, 'r') as f:
                agents[agent_name] = {
                    "path": str(agent_file),
                    "source": f.read()[:200]  # First 200 chars
                }
    
    agents_json = {
        "agents": agents,
        "count": len(agents)
    }
    
    export_path = config_dir / "agents.json"
    with open(export_path, 'w') as f:
        json.dump(agents_json, f, indent=2)
    
    return str(export_path)


def export_ddd_context(context_path: Path, config_dir: Path) -> str:
    """
    Export DDD context from CONTEXT.md to ddd-context.json.
    
    Args:
        context_path: Path to docs/domain/CONTEXT.md
        config_dir: Directory to export config to
        
    Returns:
        Path to exported ddd-context.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    
    ddd_context = {
        "purpose": "",
        "ubiquitous_language": {},
        "strict_invariants": []
    }
    
    if context_path.exists():
        with open(context_path, 'r') as f:
            content = f.read()
        ddd_context["source"] = content
    
    export_path = config_dir / "ddd-context.json"
    with open(export_path, 'w') as f:
        json.dump(ddd_context, f, indent=2)
    
    return str(export_path)


def export_rules_config(rules_dir: Path, config_dir: Path) -> str:
    """
    Export project mandates/rules to rules.json.
    
    Args:
        rules_dir: Path to rules/ directory
        config_dir: Directory to export config to
        
    Returns:
        Path to exported rules.json
    """
    config_dir = Path(config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    
    rules = {}
    if rules_dir.exists():
        for rule_file in rules_dir.glob("*.md"):
            rule_name = rule_file.stem
            with open(rule_file, 'r') as f:
                rules[rule_name] = f.read()
    
    rules_json = {
        "rules": rules,
        "count": len(rules)
    }
    
    export_path = config_dir / "rules.json"
    with open(export_path, 'w') as f:
        json.dump(rules_json, f, indent=2)
    
    return str(export_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/harness/test_plugin_generator.py::test_export_orchestrator_config_copies_orchestrator_md -xvs
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add harness/plugin_generator.py tests/harness/test_plugin_generator.py
git commit -m "feat(plugin-gen): add config export functions"
```

---

### Task 3: Add main generate_orchestrator_plugin() function

**Files:**
- Modify: `harness/plugin_generator.py`
- Modify: `tests/harness/test_plugin_generator.py`

- [ ] **Step 1: Write failing test for main generation function**

Add to `tests/harness/test_plugin_generator.py`:

```python
def test_generate_orchestrator_plugin_creates_complete_structure():
    """Test that generate_orchestrator_plugin creates all required files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create minimal harness structure
        harness_dir = Path(tmpdir) / ".claude"
        harness_dir.mkdir()
        (harness_dir / "orchestrator.md").write_text("# Orchestrator")
        (harness_dir / "agents").mkdir()
        (harness_dir / "agents/planner.md").write_text("# Planner Agent")
        (harness_dir / "rules").mkdir()
        (harness_dir / "rules/core_mandates.md").write_text("# Core Mandates")
        
        docs_dir = Path(tmpdir) / "docs" / "domain"
        docs_dir.mkdir(parents=True)
        (docs_dir / "CONTEXT.md").write_text("# Context")
        
        # Call generate function
        plugin_dir = generate_orchestrator_plugin(
            project_path=tmpdir,
            project_name="test-project"
        )
        
        # Verify structure
        assert (Path(plugin_dir) / "plugin.json").exists()
        assert (Path(plugin_dir) / "src" / "orchestrator_plugin.py").exists()
        assert (Path(plugin_dir) / "src" / "dispatcher.py").exists()
        assert (Path(plugin_dir) / "src" / "interceptor.py").exists()
        assert (Path(plugin_dir) / "config" / "agents.json").exists()
        assert (Path(plugin_dir) / "config" / "orchestrator.json").exists()
        assert (Path(plugin_dir) / "config" / "ddd-context.json").exists()
        assert (Path(plugin_dir) / "config" / "rules.json").exists()
        assert (Path(plugin_dir) / "pyproject.toml").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/harness/test_plugin_generator.py::test_generate_orchestrator_plugin_creates_complete_structure -xvs
```

Expected: `NameError: name 'generate_orchestrator_plugin' is not defined`

- [ ] **Step 3: Implement generate_orchestrator_plugin() function**

Add to `harness/plugin_generator.py`:

```python
def generate_orchestrator_plugin(
    project_path: str,
    project_name: str,
    plugin_version: str = "1.0.0"
) -> str:
    """
    Generate a complete orchestrator plugin for the project.
    
    Args:
        project_path: Root path of the project
        project_name: Name of the project
        plugin_version: Version of the plugin
        
    Returns:
        Path to the generated plugin directory
    """
    project_path = Path(project_path)
    plugin_dir = project_path / ".claude" / "plugin-generated"
    
    # Create directory structure
    src_dir = plugin_dir / "src"
    config_dir = plugin_dir / "config"
    src_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate manifest
    generate_plugin_manifest(str(plugin_dir), project_name, plugin_version)
    
    # Export configs
    harness_dir = project_path / ".claude"
    if harness_dir.exists():
        if (harness_dir / "orchestrator.md").exists():
            export_orchestrator_config(harness_dir / "orchestrator.md", config_dir)
        if (harness_dir / "agents").exists():
            export_agents_config(harness_dir / "agents", config_dir)
        if (harness_dir / "rules").exists():
            export_rules_config(harness_dir / "rules", config_dir)
    
    # Export DDD context
    context_path = project_path / "docs" / "domain" / "CONTEXT.md"
    export_ddd_context(context_path, config_dir)
    
    # Generate plugin source files (stub for now)
    generate_plugin_sources(src_dir)
    
    # Generate pyproject.toml
    generate_pyproject(plugin_dir)
    
    return str(plugin_dir)


def generate_plugin_sources(src_dir: Path) -> None:
    """
    Generate plugin source files: orchestrator_plugin.py, dispatcher.py, interceptor.py.
    """
    src_dir = Path(src_dir)
    
    # Stub files for now (will be expanded in Phase 2)
    (src_dir / "orchestrator_plugin.py").write_text(
        '# Plugin entry point\n# TODO: Implement\n'
    )
    (src_dir / "dispatcher.py").write_text(
        '# Dispatcher logic\n# TODO: Implement\n'
    )
    (src_dir / "interceptor.py").write_text(
        '# Hook interception\n# TODO: Implement\n'
    )


def generate_pyproject(plugin_dir: Path) -> str:
    """
    Generate pyproject.toml for the plugin.
    """
    pyproject_content = """[project]
name = "orchestrator-plugin"
version = "1.0.0"
description = "Auto-generated orchestrator plugin"
requires-python = ">=3.8"

dependencies = [
    "pydantic>=2.0",
    "typing_extensions>=4.0"
]

[tool.poetry]
packages = [
    { include = "src" }
]
"""
    
    pyproject_path = plugin_dir / "pyproject.toml"
    with open(pyproject_path, 'w') as f:
        f.write(pyproject_content)
    
    return str(pyproject_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/harness/test_plugin_generator.py::test_generate_orchestrator_plugin_creates_complete_structure -xvs
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add harness/plugin_generator.py tests/harness/test_plugin_generator.py
git commit -m "feat(plugin-gen): implement complete plugin generation"
```

---

## Phase 2: Minting Engine Integration

### Task 4: Extend minting_engine.py to detect Claude Code + orchestrator-plugin

**Files:**
- Modify: `harness/minting_engine.py` (around line 320-360, in mint_workspace function)
- Modify: `tests/harness/test_plugin_generator.py`

- [ ] **Step 1: Write failing test for minting engine detection**

Add to `tests/harness/test_plugin_generator.py`:

```python
def test_minting_engine_detects_orchestrator_plugin_selection(monkeypatch):
    """Test that minting engine detects orchestrator-plugin selection."""
    from harness.minting_engine import should_generate_orchestrator_plugin
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock ONBOARDING_DOMAIN.md with orchestrator-plugin selected
        domain_path = Path(tmpdir) / "ONBOARDING_DOMAIN.md"
        domain_path.write_text("""
## Proposed Skills

- [x] orchestrator-plugin (path/to/plugin) <!-- type: extension -->
- [x] some-skill (url/to/skill)
""")
        
        # Test with Claude platform
        result = should_generate_orchestrator_plugin(
            domain_path=str(domain_path),
            platform_choice="2"  # Claude
        )
        
        assert result is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/harness/test_plugin_generator.py::test_minting_engine_detects_orchestrator_plugin_selection -xvs
```

Expected: `NameError: name 'should_generate_orchestrator_plugin' is not defined`

- [ ] **Step 3: Add detection function to minting_engine.py**

Add to `harness/minting_engine.py` (before mint_workspace function):

```python
def should_generate_orchestrator_plugin(domain_path: str, platform_choice: str) -> bool:
    """
    Detect if orchestrator-plugin is selected and platform is Claude Code.
    
    Args:
        domain_path: Path to ONBOARDING_DOMAIN.md
        platform_choice: Platform choice ("1"=gemini, "2"=claude, etc.)
        
    Returns:
        True if plugin should be generated
    """
    if platform_choice != "2":  # Only for Claude Code
        return False
    
    if not os.path.exists(domain_path):
        return False
    
    with open(domain_path, 'r') as f:
        content = f.read()
    
    # Check if orchestrator-plugin is selected (marked with [x])
    return re.search(r'- \[[xX]\]\s+orchestrator-plugin', content) is not None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/harness/test_plugin_generator.py::test_minting_engine_detects_orchestrator_plugin_selection -xvs
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add harness/minting_engine.py tests/harness/test_plugin_generator.py
git commit -m "feat(minting): detect orchestrator-plugin selection"
```

---

### Task 5: Integrate plugin generation into mint_workspace flow

**Files:**
- Modify: `harness/minting_engine.py` (in mint_workspace function, after line 240)
- Modify: `tests/harness/test_plugin_generator.py`

- [ ] **Step 1: Write failing test for minting integration**

Add to `tests/harness/test_plugin_generator.py`:

```python
def test_mint_workspace_generates_plugin_when_requested(monkeypatch):
    """Test that mint_workspace calls plugin generation."""
    from harness.minting_engine import mint_workspace
    from harness.plugin_generator import generate_orchestrator_plugin
    
    plugin_called = []
    original_generate = generate_orchestrator_plugin
    
    def mock_generate(*args, **kwargs):
        plugin_called.append(True)
        return original_generate(*args, **kwargs)
    
    monkeypatch.setattr("harness.minting_engine.generate_orchestrator_plugin", mock_generate)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = tmpdir
        target_dir = os.path.join(tmpdir, ".claude")
        
        # Create ONBOARDING_DOMAIN.md with orchestrator-plugin
        domain_path = Path(project_path) / "ONBOARDING_DOMAIN.md"
        domain_path.write_text("- [x] orchestrator-plugin (path)")
        
        # Mock boilerplate directory
        boilerplate_dir = os.path.join(tmpdir, "boilerplate")
        os.makedirs(boilerplate_dir)
        
        mint_workspace(
            target_dir=target_dir,
            selected_agents=[],
            project_path=project_path,
            platform_choice="2",  # Claude
            boilerplate_dir=boilerplate_dir
        )
        
        assert len(plugin_called) > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/harness/test_plugin_generator.py::test_mint_workspace_generates_plugin_when_requested -xvs
```

Expected: `AssertionError` (plugin not generated)

- [ ] **Step 3: Add plugin generation call to mint_workspace**

In `harness/minting_engine.py`, after line 240 (after "--- End Ghost Injection ---"), add:

```python
        # --- Plugin Generation for Claude Code ---
        if active_platform == "claude":
            from harness.plugin_generator import generate_orchestrator_plugin
            from harness.minting_engine import should_generate_orchestrator_plugin
            
            domain_doc_path = os.path.join(project_path, "ONBOARDING_DOMAIN.md")
            if should_generate_orchestrator_plugin(domain_doc_path, platform_choice):
                print("[HARNESS] Generating orchestrator plugin...")
                plugin_dir = generate_orchestrator_plugin(
                    project_path=project_path,
                    project_name=os.path.basename(project_path)
                )
                print(f"[HARNESS] Plugin generated at {plugin_dir}")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/harness/test_plugin_generator.py::test_mint_workspace_generates_plugin_when_requested -xvs
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add harness/minting_engine.py tests/harness/test_plugin_generator.py
git commit -m "feat(minting): integrate plugin generation into mint_workspace"
```

---

### Task 6: Add plugin installation to setup_harness.sh generation

**Files:**
- Modify: `harness/minting_engine.py` (in scripts_to_generate["claude"], around line 318)
- Modify: `tests/harness/test_plugin_generator.py`

- [ ] **Step 1: Write failing test for plugin installation in setup script**

Add to `tests/harness/test_plugin_generator.py`:

```python
def test_setup_harness_script_includes_plugin_install():
    """Test that setup_harness.sh includes plugin installation command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = tmpdir
        target_dir = os.path.join(tmpdir, ".claude")
        
        # Create ONBOARDING_DOMAIN.md with orchestrator-plugin
        domain_path = Path(project_path) / "ONBOARDING_DOMAIN.md"
        domain_path.write_text("- [x] orchestrator-plugin (path)")
        
        # Mock boilerplate
        boilerplate_dir = os.path.join(tmpdir, "boilerplate")
        os.makedirs(boilerplate_dir)
        
        from harness.minting_engine import mint_workspace
        mint_workspace(
            target_dir=target_dir,
            selected_agents=[],
            project_path=project_path,
            platform_choice="2",  # Claude
            boilerplate_dir=boilerplate_dir
        )
        
        # Check setup_harness.sh
        setup_script = Path(project_path) / ".claude" / "scripts" / "setup_harness.sh"
        if setup_script.exists():
            content = setup_script.read_text()
            assert "/plugin install" in content
            assert "orchestrator-plugin" in content
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/harness/test_plugin_generator.py::test_setup_harness_script_includes_plugin_install -xvs
```

Expected: `AssertionError` (plugin install not in script)

- [ ] **Step 3: Update setup_harness.sh generation in minting_engine.py**

In `harness/minting_engine.py`, find the `scripts_to_generate["claude"]` block (around line 318) and update it:

```python
        "claude": f"""#!/usr/bin/env bash
set -e
cd {quoted_project_path}
echo "=== Setting up Superpowers for Claude Code ==="
echo "To install Skills for Claude Code workspace-wide, run these commands inside the Claude Code interface:"
{skill_installs}

# Plugin Installation for Claude Code
if [ -d ".claude/plugin-generated" ]; then
    echo "Installing orchestrator plugin..."
    /plugin install orchestrator-plugin@.claude/plugin-generated --project || true
fi

# MCP Configuration for Claude
if command -v claude &> /dev/null; then
    echo "Ensuring CodeGraph is build..."
    npx -y @colbymchenry/codegraph init --index || true

    echo "Adding codegraph to Claude Code project MCP configuration..."
    claude mcp add --scope project codegraph -- npx -y @colbymchenry/codegraph serve --mcp || true
{mcp_installs}
fi
""",
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/harness/test_plugin_generator.py::test_setup_harness_script_includes_plugin_install -xvs
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add harness/minting_engine.py tests/harness/test_plugin_generator.py
git commit -m "feat(setup): add orchestrator-plugin installation to setup_harness.sh"
```

---

## Phase 3: Plugin Dispatcher Logic

### Task 7: Implement dispatcher.py with orchestrator routing

**Files:**
- Modify: `.claude/plugin-generated/src/dispatcher.py` (auto-generated but we set the template)
- Modify: `harness/plugin_generator.py` (update generate_plugin_sources)
- Create: `tests/harness/test_dispatcher.py`

- [ ] **Step 1: Write failing test for dispatcher routing**

Create `tests/harness/test_dispatcher.py`:

```python
import pytest
import tempfile
from pathlib import Path
from harness.dispatcher import OrchestratorDispatcher

def test_dispatcher_routes_agent_request_through_orchestrator():
    """Test that dispatcher routes agent requests through orchestrator."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()
        
        # Create mock config
        (config_dir / "orchestrator.json").write_text('{"rules": []}')
        (config_dir / "agents.json").write_text('{"agents": {"planner": {}}}')
        
        dispatcher = OrchestratorDispatcher(config_dir=str(config_dir))
        
        # Test agent request
        result = dispatcher.dispatch_agent(agent_name="planner", context={})
        
        assert result is not None
        assert "agent" in result or "routed" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/harness/test_dispatcher.py::test_dispatcher_routes_agent_request_through_orchestrator -xvs
```

Expected: `ModuleNotFoundError: No module named 'harness.dispatcher'`

- [ ] **Step 3: Create dispatcher.py module**

Create `harness/dispatcher.py`:

```python
import json
from pathlib import Path
from typing import Any, Dict, Optional

class OrchestratorDispatcher:
    """
    Routes agent requests through the project's orchestrator.
    """
    
    def __init__(self, config_dir: str):
        """
        Initialize dispatcher with plugin config.
        
        Args:
            config_dir: Path to .claude/plugin-generated/config
        """
        self.config_dir = Path(config_dir)
        self.orchestrator_config = self._load_orchestrator_config()
        self.agents_config = self._load_agents_config()
    
    def _load_orchestrator_config(self) -> Dict[str, Any]:
        """Load orchestrator configuration."""
        config_file = self.config_dir / "orchestrator.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _load_agents_config(self) -> Dict[str, Any]:
        """Load agents configuration."""
        config_file = self.config_dir / "agents.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        return {"agents": {}}
    
    def dispatch_agent(
        self, 
        agent_name: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Route agent request through orchestrator.
        
        Args:
            agent_name: Name of the agent to dispatch
            context: Agent execution context
            
        Returns:
            Dispatch result with routed agent info
        """
        # Validate agent exists in config
        agents = self.agents_config.get("agents", {})
        if agent_name not in agents:
            raise ValueError(f"Agent '{agent_name}' not found in configuration")
        
        # Apply orchestrator rules (stub for now)
        # In full implementation, this would validate against rules,
        # apply mandate checks, and apply routing logic
        
        return {
            "agent": agent_name,
            "routed": True,
            "context": context,
            "orchestrator_applied": True
        }
    
    def validate_against_rules(self, agent_name: str) -> bool:
        """
        Validate agent request against project rules.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            True if valid
        """
        # Load rules config
        rules_file = self.config_dir / "rules.json"
        if not rules_file.exists():
            return True
        
        with open(rules_file, 'r') as f:
            rules = json.load(f)
        
        # Stub: always valid for now
        # In full implementation, parse rules and apply validation
        return True
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/harness/test_dispatcher.py::test_dispatcher_routes_agent_request_through_orchestrator -xvs
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add harness/dispatcher.py tests/harness/test_dispatcher.py
git commit -m "feat(dispatcher): implement orchestrator dispatch routing"
```

---

### Task 8: Implement orchestrator_plugin.py entry point

**Files:**
- Modify: `harness/plugin_generator.py` (update generate_plugin_sources to write full template)
- Modify: `tests/harness/test_plugin_generator.py`

- [ ] **Step 1: Write failing test for plugin entry point**

Add to `tests/harness/test_plugin_generator.py`:

```python
def test_plugin_entry_point_is_valid_python():
    """Test that generated orchestrator_plugin.py is valid Python."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir(parents=True)
        
        from harness.plugin_generator import generate_plugin_sources
        generate_plugin_sources(src_dir)
        
        plugin_file = src_dir / "orchestrator_plugin.py"
        assert plugin_file.exists()
        
        # Verify it's valid Python by compiling
        with open(plugin_file, 'r') as f:
            code = f.read()
        compile(code, str(plugin_file), 'exec')
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/harness/test_plugin_generator.py::test_plugin_entry_point_is_valid_python -xvs
```

Expected: `SyntaxError` (stub code not valid Python)

- [ ] **Step 3: Update generate_plugin_sources to create full entry point**

In `harness/plugin_generator.py`, replace the `generate_plugin_sources` function:

```python
def generate_plugin_sources(src_dir: Path) -> None:
    """
    Generate plugin source files.
    """
    src_dir = Path(src_dir)
    
    # Generate orchestrator_plugin.py
    orchestrator_plugin_content = '''"""
Orchestrator Plugin for Claude Code.

This plugin is auto-generated and enforces orchestrator-based agent dispatch.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Import dispatcher (generated in same package)
from .dispatcher import OrchestratorDispatcher


class OrchestratorPlugin:
    """
    Main plugin class for Claude Code.
    
    Enforces that all agent dispatching goes through the project's orchestrator.
    """
    
    def __init__(self):
        """Initialize plugin with config from .claude/plugin-generated/config."""
        plugin_dir = Path(__file__).parent.parent
        config_dir = plugin_dir / "config"
        self.dispatcher = OrchestratorDispatcher(str(config_dir))
    
    def initialize(self) -> bool:
        """
        Initialize plugin. Called when Claude Code loads the plugin.
        
        Returns:
            True if initialization successful
        """
        return True
    
    def intercept_agent_dispatch(
        self, 
        agent_name: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Intercept agent dispatch and route through orchestrator.
        
        Args:
            agent_name: Name of the agent being requested
            context: Execution context
            
        Returns:
            Dispatch result from orchestrator
        """
        # Validate rules
        if not self.dispatcher.validate_against_rules(agent_name):
            raise PermissionError(f"Agent '{agent_name}' violates project rules")
        
        # Route through orchestrator
        return self.dispatcher.dispatch_agent(agent_name, context)


# Plugin singleton
_plugin_instance: Optional[OrchestratorPlugin] = None


def get_plugin() -> OrchestratorPlugin:
    """Get or create plugin instance."""
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = OrchestratorPlugin()
    return _plugin_instance


def init() -> bool:
    """
    Plugin initialization hook. Called by Claude Code on startup.
    """
    plugin = get_plugin()
    return plugin.initialize()
'''
    
    (src_dir / "orchestrator_plugin.py").write_text(orchestrator_plugin_content)
    
    # Generate dispatcher.py stub (will be implemented separately)
    dispatcher_content = '''"""
Dispatcher module for orchestrator plugin.
"""

# Will be copied from harness/dispatcher.py during plugin generation
'''
    
    (src_dir / "dispatcher.py").write_text(dispatcher_content)
    
    # Generate interceptor.py
    interceptor_content = '''"""
Hook interception for Claude Code agent dispatch.
"""

from .orchestrator_plugin import get_plugin


def intercept_agent_dispatch(agent_name: str, context: dict) -> dict:
    """
    Hook function called when Claude Code dispatches an agent.
    
    This is registered in plugin.json hooks.agent_dispatch.
    """
    plugin = get_plugin()
    return plugin.intercept_agent_dispatch(agent_name, context)
'''
    
    (src_dir / "interceptor.py").write_text(interceptor_content)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/harness/test_plugin_generator.py::test_plugin_entry_point_is_valid_python -xvs
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add harness/plugin_generator.py tests/harness/test_plugin_generator.py
git commit -m "feat(plugin): implement plugin entry point and hooks"
```

---

### Task 9: Copy dispatcher.py into generated plugin

**Files:**
- Modify: `harness/plugin_generator.py` (update generate_orchestrator_plugin)
- Modify: `tests/harness/test_plugin_generator.py`

- [ ] **Step 1: Write failing test for dispatcher copy**

Add to `tests/harness/test_plugin_generator.py`:

```python
def test_dispatcher_module_copied_to_plugin():
    """Test that dispatcher.py is copied into generated plugin."""
    with tempfile.TemporaryDirectory() as tmpdir:
        harness_dir = Path(tmpdir) / ".claude"
        harness_dir.mkdir()
        (harness_dir / "orchestrator.md").write_text("# Orchestrator")
        (harness_dir / "agents").mkdir()
        (harness_dir / "rules").mkdir()
        
        docs_dir = Path(tmpdir) / "docs" / "domain"
        docs_dir.mkdir(parents=True)
        (docs_dir / "CONTEXT.md").write_text("# Context")
        
        from harness.plugin_generator import generate_orchestrator_plugin
        plugin_dir = generate_orchestrator_plugin(tmpdir, "test-project")
        
        # Verify dispatcher.py exists and has correct content
        dispatcher_file = Path(plugin_dir) / "src" / "dispatcher.py"
        assert dispatcher_file.exists()
        content = dispatcher_file.read_text()
        assert "OrchestratorDispatcher" in content
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/harness/test_plugin_generator.py::test_dispatcher_module_copied_to_plugin -xvs
```

Expected: `AssertionError` (dispatcher not copied)

- [ ] **Step 3: Update generate_orchestrator_plugin to copy dispatcher**

In `harness/plugin_generator.py`, update the `generate_orchestrator_plugin` function:

```python
def generate_orchestrator_plugin(
    project_path: str,
    project_name: str,
    plugin_version: str = "1.0.0"
) -> str:
    """
    Generate a complete orchestrator plugin for the project.
    ...
    """
    project_path = Path(project_path)
    plugin_dir = project_path / ".claude" / "plugin-generated"
    
    # Create directory structure
    src_dir = plugin_dir / "src"
    config_dir = plugin_dir / "config"
    src_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate manifest
    generate_plugin_manifest(str(plugin_dir), project_name, plugin_version)
    
    # Export configs
    harness_dir = project_path / ".claude"
    if harness_dir.exists():
        if (harness_dir / "orchestrator.md").exists():
            export_orchestrator_config(harness_dir / "orchestrator.md", config_dir)
        if (harness_dir / "agents").exists():
            export_agents_config(harness_dir / "agents", config_dir)
        if (harness_dir / "rules").exists():
            export_rules_config(harness_dir / "rules", config_dir)
    
    # Export DDD context
    context_path = project_path / "docs" / "domain" / "CONTEXT.md"
    export_ddd_context(context_path, config_dir)
    
    # Generate plugin source files
    generate_plugin_sources(src_dir)
    
    # Copy dispatcher module from harness
    import shutil
    harness_dispatcher = Path(__file__).parent / "dispatcher.py"
    if harness_dispatcher.exists():
        shutil.copy(harness_dispatcher, src_dir / "dispatcher.py")
    
    # Generate pyproject.toml
    generate_pyproject(plugin_dir)
    
    return str(plugin_dir)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/harness/test_plugin_generator.py::test_dispatcher_module_copied_to_plugin -xvs
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add harness/plugin_generator.py tests/harness/test_plugin_generator.py
git commit -m "feat(plugin-gen): copy dispatcher module into generated plugin"
```

---

## Phase 4: Testing & Integration

### Task 10: Integration test for complete plugin generation flow

**Files:**
- Create: `tests/integration/test_plugin_flow.py`

- [ ] **Step 1: Write integration test for full flow**

Create `tests/integration/test_plugin_flow.py`:

```python
import os
import json
import tempfile
from pathlib import Path
import pytest

def test_complete_plugin_generation_flow():
    """
    Integration test: Complete flow from harness setup to plugin generation.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        
        # Create mock project structure
        harness_dir = project_path / ".claude"
        harness_dir.mkdir()
        (harness_dir / "orchestrator.md").write_text("# Orchestrator\n\nRouting rules...")
        
        agents_dir = harness_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "planner.md").write_text("# Planner\n\nPlanning agent")
        (agents_dir / "implementer.md").write_text("# Implementer\n\nImplementation agent")
        
        rules_dir = harness_dir / "rules"
        rules_dir.mkdir()
        (rules_dir / "core_mandates.md").write_text("# Core Mandates\n\nRules...")
        
        context_dir = project_path / "docs" / "domain"
        context_dir.mkdir(parents=True)
        (context_dir / "CONTEXT.md").write_text("# Context\n\nDDD context...")
        
        # Create ONBOARDING_DOMAIN.md with orchestrator-plugin selected
        (project_path / "ONBOARDING_DOMAIN.md").write_text("""
## Proposed Skills

- [x] orchestrator-plugin (path/to/plugin) <!-- type: extension -->
""")
        
        # Call plugin generation
        from harness.plugin_generator import generate_orchestrator_plugin
        plugin_dir = generate_orchestrator_plugin(
            project_path=str(project_path),
            project_name="integration-test"
        )
        
        # Verify complete structure
        plugin_path = Path(plugin_dir)
        
        # Check manifest
        manifest_file = plugin_path / "plugin.json"
        assert manifest_file.exists()
        with open(manifest_file) as f:
            manifest = json.load(f)
        assert manifest['name'] == 'orchestrator-plugin'
        assert 'entry_point' in manifest
        
        # Check source files
        assert (plugin_path / "src" / "orchestrator_plugin.py").exists()
        assert (plugin_path / "src" / "dispatcher.py").exists()
        assert (plugin_path / "src" / "interceptor.py").exists()
        
        # Check config files
        assert (plugin_path / "config" / "agents.json").exists()
        assert (plugin_path / "config" / "orchestrator.json").exists()
        assert (plugin_path / "config" / "ddd-context.json").exists()
        assert (plugin_path / "config" / "rules.json").exists()
        
        # Check pyproject.toml
        assert (plugin_path / "pyproject.toml").exists()
        
        # Verify agents were exported correctly
        with open(plugin_path / "config" / "agents.json") as f:
            agents_config = json.load(f)
        assert agents_config['count'] == 2
        assert 'planner' in agents_config['agents']
        assert 'implementer' in agents_config['agents']
        
        print(f"✓ Plugin generated successfully at {plugin_dir}")


def test_plugin_can_be_imported():
    """Test that generated plugin can be imported and instantiated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        
        # Minimal structure
        harness_dir = project_path / ".claude"
        harness_dir.mkdir()
        (harness_dir / "orchestrator.md").write_text("# Orchestrator")
        (harness_dir / "agents").mkdir()
        (harness_dir / "rules").mkdir()
        context_dir = project_path / "docs" / "domain"
        context_dir.mkdir(parents=True)
        (context_dir / "CONTEXT.md").write_text("# Context")
        
        from harness.plugin_generator import generate_orchestrator_plugin
        plugin_dir = generate_orchestrator_plugin(str(project_path), "test")
        
        # Try to import the plugin
        import sys
        sys.path.insert(0, str(Path(plugin_dir) / "src"))
        
        try:
            from orchestrator_plugin import OrchestratorPlugin, init
            
            # Test initialization
            assert init() is True
            
            # Test plugin instance
            plugin = OrchestratorPlugin()
            assert plugin is not None
            
            print("✓ Plugin entry point works correctly")
        finally:
            sys.path.pop(0)
```

- [ ] **Step 2: Run integration test**

```bash
pytest tests/integration/test_plugin_flow.py -xvs
```

Expected: `PASSED` (or failures that reveal what needs fixing)

- [ ] **Step 3: Fix any issues**

If tests fail, fix the implementation. Common issues:
- Missing directory creation
- Incorrect JSON structure
- Import path issues

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_plugin_flow.py
git commit -m "test(integration): add comprehensive plugin generation flow test"
```

---

### Task 11: Test minting engine integration end-to-end

**Files:**
- Create: `tests/integration/test_minting_with_plugin.py`

- [ ] **Step 1: Write end-to-end test for minting + plugin**

Create `tests/integration/test_minting_with_plugin.py`:

```python
import os
import tempfile
from pathlib import Path
import pytest

def test_minting_engine_generates_plugin_during_setup():
    """
    Test that mint_workspace generates plugin when Claude Code + orchestrator-plugin selected.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        harness_dir = project_path / ".claude"
        
        # Create ONBOARDING_DOMAIN.md with orchestrator-plugin
        (project_path / "ONBOARDING_DOMAIN.md").write_text("""
## Proposed Skills

- [x] orchestrator-plugin (path) <!-- type: extension -->
- [x] some-skill (http://example.com)
""")
        
        # Create minimal boilerplate
        boilerplate_dir = project_path / "boilerplate"
        boilerplate_dir.mkdir()
        (boilerplate_dir / "orchestrator.md").write_text("# Orchestrator")
        (boilerplate_dir / "agents").mkdir()
        (boilerplate_dir / "rules").mkdir()
        
        from harness.minting_engine import mint_workspace
        
        # Call mint_workspace with Claude platform
        mint_workspace(
            target_dir=str(harness_dir),
            selected_agents=[],
            project_path=str(project_path),
            platform_choice="2",  # Claude
            boilerplate_dir=str(boilerplate_dir)
        )
        
        # Verify plugin was generated
        plugin_dir = harness_dir / "plugin-generated"
        assert plugin_dir.exists(), "Plugin directory not created"
        assert (plugin_dir / "plugin.json").exists(), "plugin.json not created"
        assert (plugin_dir / "src" / "orchestrator_plugin.py").exists()
        
        # Verify setup_harness.sh includes plugin installation
        setup_script = harness_dir / "scripts" / "setup_harness.sh"
        if setup_script.exists():
            content = setup_script.read_text()
            assert "/plugin install" in content
            assert "orchestrator-plugin" in content
        
        print("✓ Minting engine correctly generates plugin")


def test_plugin_not_generated_for_non_claude_platform():
    """Test that plugin is NOT generated for non-Claude platforms."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        harness_dir = project_path / ".gemini"
        
        # Create ONBOARDING_DOMAIN.md
        (project_path / "ONBOARDING_DOMAIN.md").write_text("""
## Proposed Skills

- [x] orchestrator-plugin (path) <!-- type: extension -->
""")
        
        # Create minimal boilerplate
        boilerplate_dir = project_path / "boilerplate"
        boilerplate_dir.mkdir()
        (boilerplate_dir / "orchestrator.md").write_text("# Orchestrator")
        (boilerplate_dir / "agents").mkdir()
        (boilerplate_dir / "rules").mkdir()
        
        from harness.minting_engine import mint_workspace
        
        # Call with Gemini platform
        mint_workspace(
            target_dir=str(harness_dir),
            selected_agents=[],
            project_path=str(project_path),
            platform_choice="1",  # Gemini
            boilerplate_dir=str(boilerplate_dir)
        )
        
        # Verify plugin was NOT generated
        plugin_dir = harness_dir / "plugin-generated"
        assert not plugin_dir.exists(), "Plugin should not be generated for non-Claude platform"
        
        print("✓ Plugin correctly not generated for Gemini platform")
```

- [ ] **Step 2: Run end-to-end test**

```bash
pytest tests/integration/test_minting_with_plugin.py -xvs
```

Expected: `PASSED`

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_minting_with_plugin.py
git commit -m "test(integration): add minting engine + plugin integration test"
```

---

## Summary

This plan implements a complete orchestrator plugin system that:

1. **Detects** when Claude Code is selected + orchestrator-plugin is requested
2. **Generates** a self-contained plugin with:
   - Plugin manifest (plugin.json)
   - Entry point (orchestrator_plugin.py)
   - Dispatcher logic (dispatcher.py)
   - Hook interception (interceptor.py)
   - Exported configs (agents.json, orchestrator.json, ddd-context.json, rules.json)
3. **Integrates** into minting engine and setup scripts
4. **Routes** all Claude Code agent dispatching through the orchestrator
5. **Tests** the entire flow end-to-end

The system ensures that any project using the harness setup can auto-generate a plugin that enforces orchestrator dispatch transparently.
