# Harness Infrastructure Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Superpowers Agentic Harness infrastructure to eliminate "magic" string replacements, fix fragile file-locking state management, enforce strict testing boundaries, and integrate professional DeepEval benchmarking.

**Architecture:** The project structure will be modernized to use a `src/` layout. The `minting_engine` will transition from `.replace()` chains to a custom-delimited Jinja2 rendering pipeline. The `dispatcher` will transition from directory-based file locking to a SQLite database utilizing WAL mode and TTL-based leases for safe concurrency.

**Tech Stack:** Python 3.10+, Pytest, Jinja2, SQLite3, DeepEval, Mise.

---

### Task 1: Repository Extraction & Hygiene

**Files:**
- Create/Modify: `.gitignore`
- Move: `chat/` -> `../chatbot/`
- Delete: `out/`, `artifacts/`, `test_repro_dir/` (if existing)

- [ ] **Step 1: Write tests for hygiene**
  *(Not strictly applicable for moving external directories, but we will write a quick shell check to verify.)*
```bash
cat << 'EOF' > test_hygiene.sh
#!/bin/bash
if [ -d "chat" ]; then echo "FAIL: chat exists"; exit 1; fi
if [ -d "out" ]; then echo "FAIL: out exists"; exit 1; fi
echo "PASS"
EOF
chmod +x test_hygiene.sh
```

- [ ] **Step 2: Run test to verify it fails**
Run: `./test_hygiene.sh`
Expected: FAIL: chat exists

- [ ] **Step 3: Implement extraction and cleanup**
```bash
# Move chat out of the repo entirely
mv chat ../chatbot

# Remove junk directories
rm -rf out artifacts test_repro_dir local_outputs

# Update gitignore
cat << 'EOF' >> .gitignore

# Harness Runtime & Debug Junk
out/
artifacts/
test_repro_dir/
local_outputs/
.harness_state.db*
EOF
```

- [ ] **Step 4: Run test to verify it passes**
Run: `./test_hygiene.sh`
Expected: PASS

- [ ] **Step 5: Clean up test script and commit**
```bash
rm test_hygiene.sh
git add -A
git commit -m "chore: extract chat application and purge debug directories"
```

---

### Task 2: Test Directory Reorganization

**Files:**
- Create: `scripts/maintenance/`, `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/benchmarks/`
- Move: `tests/fix_*.py`, `tests/patch_*.py`, `tests/run_debug.py` -> `scripts/maintenance/`
- Move: `tests/test_*.py` -> appropriate `tests/*/` folders.

- [ ] **Step 1: Write shell script to verify structure**
```bash
cat << 'EOF' > test_structure.sh
#!/bin/bash
if ls tests/fix_*.py 1> /dev/null 2>&1; then echo "FAIL: fix scripts in tests/"; exit 1; fi
if [ ! -d "tests/unit" ]; then echo "FAIL: unit dir missing"; exit 1; fi
echo "PASS"
EOF
chmod +x test_structure.sh
```

- [ ] **Step 2: Run test to verify it fails**
Run: `./test_structure.sh`
Expected: FAIL: fix scripts in tests/

- [ ] **Step 3: Implement restructuring**
```bash
mkdir -p scripts/maintenance tests/unit tests/integration tests/e2e tests/benchmarks

# Move maintenance scripts
mv tests/fix_*.py scripts/maintenance/ 2>/dev/null || true
mv tests/patch_*.py scripts/maintenance/ 2>/dev/null || true
mv tests/run_debug.py scripts/maintenance/ 2>/dev/null || true
mv tests/sandbox_test.py scripts/maintenance/ 2>/dev/null || true
mv tests/repro_unbound_local.py scripts/maintenance/ 2>/dev/null || true

# Move actual tests (rough categorization, can be refined later)
mv tests/test_cli*.py tests/e2e/ 2>/dev/null || true
mv tests/test_e2e_flow.py tests/e2e/ 2>/dev/null || true

mv tests/test_minting*.py tests/integration/ 2>/dev/null || true
mv tests/test_plugin_generator.py tests/integration/ 2>/dev/null || true
mv tests/test_dynamic_manifest.py tests/integration/ 2>/dev/null || true
mv tests/test_platform_*.py tests/integration/ 2>/dev/null || true

mv tests/test_*.py tests/unit/ 2>/dev/null || true
```

- [ ] **Step 4: Run test to verify it passes**
Run: `./test_structure.sh`
Expected: PASS

- [ ] **Step 5: Clean up and commit**
```bash
rm test_structure.sh
git add tests/ scripts/
git commit -m "test: reorganize test directory and extract maintenance scripts"
```

---

### Task 3: Package Restructuring (`src/` layout)

**Files:**
- Create: `src/harness/templates/`
- Move: `harness/*.py` -> `src/harness/`
- Move: `boilerplate-agent/*` -> `src/harness/templates/boilerplate/`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write test to verify import failure**
```python
# test_import.py
try:
    import harness.cli
    print("FAIL: Old import path works")
except ImportError:
    import sys
    sys.path.insert(0, 'src')
    import harness.cli
    print("PASS")
```

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 test_import.py`
Expected: FAIL: Old import path works

- [ ] **Step 3: Implement restructuring**
```bash
mkdir -p src/harness/templates
mv harness/*.py src/harness/
touch src/harness/__init__.py
mv boilerplate-agent src/harness/templates/boilerplate
rm -rf harness  # Remove old empty dir
```

Modify `pyproject.toml` (replace tools section):
```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["harness*"]

[tool.setuptools.package-data]
"harness" = ["templates/boilerplate/**/*", "templates/boilerplate/**/.*"]
```

- [ ] **Step 4: Run test to verify it passes**
Run: `python3 test_import.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
rm test_import.py
git add src/ pyproject.toml harness/ boilerplate-agent/
git commit -m "refactor: migrate to src layout and bundle templates"
```

---

### Task 4: Jinja2 Templating Engine Integration

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/harness/minting_engine.py`

- [ ] **Step 1: Add dependencies and write failing test**
Modify `pyproject.toml` dependencies:
```toml
dependencies = [
    "Jinja2>=3.1.0"
]
```
Run `pip install -e .` to install Jinja2.

Create `tests/unit/test_renderer.py`:
```python
import pytest
from harness.minting_engine import TemplateRenderer

def test_template_renderer():
    renderer = TemplateRenderer()
    template = "## Agent\n<!--% if active %-->Hello <!--$ name $--><!--% endif %-->"
    context = {"active": True, "name": "World"}
    result = renderer.render_string(template, context)
    assert result == "## Agent\nHello World"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_renderer.py -v`
Expected: FAIL (TemplateRenderer not imported/defined)

- [ ] **Step 3: Write minimal implementation**
Add to `src/harness/minting_engine.py` (at the top):
```python
from jinja2 import Environment, FileSystemLoader, BaseLoader

class TemplateRenderer:
    def __init__(self, template_dir=None):
        self.env = Environment(
            loader=FileSystemLoader(template_dir) if template_dir else BaseLoader(),
            block_start_string='<!--%',
            block_end_string='%-->',
            variable_start_string='<!--$',
            variable_end_string='$-->',
            comment_start_string='<!--#',
            comment_end_string='#-->',
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def render_string(self, source_str: str, context: dict) -> str:
        template = self.env.from_string(source_str)
        return template.render(**context)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_renderer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add pyproject.toml src/harness/minting_engine.py tests/unit/test_renderer.py
git commit -m "feat: implement Jinja2 TemplateRenderer with markdown-safe delimiters"
```

*(Note: Full conversion of `mint_workspace` logic to use the renderer will be done iteratively during implementation. This task establishes the engine.)*

---

### Task 5: SQLite WAL State Management

**Files:**
- Create: `src/harness/database.py`
- Modify: `src/harness/dispatcher.py`

- [ ] **Step 1: Write failing test**
Create `tests/unit/test_database.py`:
```python
import pytest
from harness.database import HarnessDB

def test_sqlite_lease(tmp_path):
    db_path = tmp_path / "state.db"
    db = HarnessDB(str(db_path))
    
    # Acquire lock
    assert db.acquire_lease("implementer", ttl_seconds=5) == True
    
    # Cannot acquire same active lock
    assert db.acquire_lease("implementer", ttl_seconds=5) == False
    
    # Release lock
    db.release_lease("implementer")
    
    # Can acquire again
    assert db.acquire_lease("implementer", ttl_seconds=5) == True
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_database.py -v`
Expected: FAIL (HarnessDB not found)

- [ ] **Step 3: Write minimal implementation**
Create `src/harness/database.py`:
```python
import sqlite3
import time
from typing import Dict, Any, Optional

class HarnessDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
        
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn
        
    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS leases (
                    resource_id TEXT PRIMARY KEY,
                    expires_at REAL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
    def acquire_lease(self, resource_id: str, ttl_seconds: float = 30.0) -> bool:
        now = time.time()
        expires_at = now + ttl_seconds
        
        with self._get_conn() as conn:
            try:
                # Clean up expired lease first
                conn.execute("DELETE FROM leases WHERE resource_id = ? AND expires_at < ?", (resource_id, now))
                
                # Attempt to insert new lease
                conn.execute("INSERT INTO leases (resource_id, expires_at) VALUES (?, ?)", (resource_id, expires_at))
                return True
            except sqlite3.IntegrityError:
                # Lease exists and is not expired
                return False

    def release_lease(self, resource_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM leases WHERE resource_id = ?", (resource_id,))
            
    def get_state(self, key: str) -> Optional[str]:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT value FROM state WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else None
            
    def set_state(self, key: str, value: str):
        with self._get_conn() as conn:
            conn.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, value))
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/harness/database.py tests/unit/test_database.py
git commit -m "feat: implement SQLite WAL state and lease manager"
```

---

### Task 6: Mise Integration and DeepEval Setup

**Files:**
- Create: `mise.toml`
- Modify: `pyproject.toml`
- Create: `tests/benchmarks/test_routing.py`

- [ ] **Step 1: Write failing test**
Create `tests/benchmarks/test_routing.py`:
```python
import pytest
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall

def test_routing_fidelity():
    # Simple placeholder test to verify DeepEval is installed and working
    test_case = LLMTestCase(
        input="Please plan the new feature",
        actual_output="Routing to planner.",
        tools_called=[ToolCall(name="dispatch_planner", arguments={})],
        expected_tools=[ToolCall(name="dispatch_planner", arguments={})]
    )
    metric = ToolCorrectnessMetric()
    metric.measure(test_case)
    assert metric.score >= 1.0
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/benchmarks/test_routing.py -v`
Expected: FAIL (deepeval not installed)

- [ ] **Step 3: Implement Tooling**
Update `pyproject.toml` dependencies:
```toml
dependencies = [
    "Jinja2>=3.1.0",
    "deepeval>=1.0.0" # Added DeepEval
]
```

Create `mise.toml` in the project root:
```toml
[tasks.test]
description = "Run unit and integration tests"
run = "pytest tests/unit tests/integration -v"

[tasks.benchmark]
description = "Run DeepEval agentic benchmarks"
run = "deepeval test run tests/benchmarks"

[tasks.install]
description = "Install package in editable mode"
run = "pip install -e ."
```

Run `pip install -e .`

- [ ] **Step 4: Run test to verify it passes**
Run: `mise run benchmark`
Expected: PASS (DeepEval test case executes and passes)

- [ ] **Step 5: Commit**
```bash
git add mise.toml pyproject.toml tests/benchmarks/test_routing.py
git commit -m "chore: setup mise tasks and deepeval benchmarking suite"
```
