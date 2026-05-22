# Tool Minting Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the boilerplate tool registry and fix the installation logic so that requested skills (including a guaranteed 'superpowers' skill) and MCPs are installed correctly into the workspace harness folder.

**Architecture:** We will modify `tools.json` to include universal CLI skills. We will fix the pathing bug in `cli.py` and `install_workspace_tools` to ensure tools are installed into `target_dir / harness_folder_name` instead of incorrectly relative to the project root. We will also guarantee the installation of the 'using-superpowers' skill.

**Tech Stack:** Python

---

### Task 1: Expand Tool Registry

**Files:**
- Modify: `boilerplate-agent/onboarding/tools.json`

- [ ] **Step 1: Write minimal implementation**

Update `tools.json` to include universal tools that apply beyond just web frameworks.

```json
{
  "categories": {
    "frontend": [
      {
        "name": "nextjs",
        "url": "https://raw.githubusercontent.com/PatrickJS/awesome-cline-prompts/main/prompts/nextjs.md",
        "keywords": ["react", "nextjs", "next.js", "frontend"]
      },
      {
         "name": "playwright",
         "command": "npx -y @modelcontextprotocol/server-playwright",
         "type": "mcp",
         "keywords": ["react", "nextjs", "frontend", "vue", "svelte"]
      }
    ],
    "backend": [
      {
        "name": "fastapi",
        "url": "https://raw.githubusercontent.com/PatrickJS/awesome-cline-prompts/main/prompts/fastapi.md",
        "keywords": ["fastapi", "python backend"]
      },
      {
        "name": "fetch",
        "command": "npx -y @modelcontextprotocol/server-fetch",
        "type": "mcp",
        "keywords": ["api", "rest", "graphql"]
      }
    ],
    "database": [
      {
        "name": "postgres",
        "command": "npx -y @modelcontextprotocol/server-postgres postgresql://postgres:postgres@localhost:5432/postgres",
        "type": "mcp",
        "keywords": ["postgresql", "postgres", "sql"]
      }
    ],
    "universal": [
      {
        "name": "using-superpowers",
        "url": "https://raw.githubusercontent.com/obra/superpowers/main/skills/using-superpowers/SKILL.md",
        "keywords": ["superpowers", "workflow", "mandatory"]
      },
      {
        "name": "git-mcp",
        "command": "npx -y @modelcontextprotocol/server-git",
        "type": "mcp",
        "keywords": ["git", "version control"]
      },
      {
        "name": "pytest-patterns",
        "url": "https://raw.githubusercontent.com/mattpocock/skills/main/skills/pytest-patterns/SKILL.md",
        "keywords": ["python", "testing", "pytest"]
      }
    ]
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add boilerplate-agent/onboarding/tools.json
git commit -m "fix: expand boilerplate tool registry with universal skills"
```

### Task 2: Guarantee Superpowers Skill Installation

**Files:**
- Modify: `harness/minting_engine.py`
- Test: `tests/integration/test_minting_engine.py`

- [ ] **Step 1: Write the failing test**

```python
@patch('urllib.request.urlopen')
def test_install_workspace_tools_guarantees_superpowers(mock_urlopen, tmp_path):
    target_dir = str(tmp_path)
    
    # Setup mock response for urlopen
    class MockResponse:
        def read(self): return b"# Mock Skill Content"
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
    mock_urlopen.return_value = MockResponse()
    
    os.makedirs(os.path.join(target_dir, ".gemini"), exist_ok=True)
    
    from harness.minting_engine import install_workspace_tools
    install_workspace_tools(target_dir, ".gemini", [], []) # Pass empty skills
    
    # Verify superpowers skill is downloaded anyway
    skill_path = os.path.join(target_dir, ".gemini", "skills", "using-superpowers", "SKILL.md")
    assert os.path.exists(skill_path)
    
    with open(os.path.join(target_dir, ".gemini", "skills.json"), "r") as f:
        s_data = json.load(f)
        assert "using-superpowers" in s_data["skills"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/integration/test_minting_engine.py::test_install_workspace_tools_guarantees_superpowers -v`
Expected: FAIL with `AssertionError`

- [ ] **Step 3: Write minimal implementation**

Update `install_workspace_tools` in `harness/minting_engine.py` to ensure `using-superpowers` is always in the list.

```python
def install_workspace_tools(target_dir: str, harness_folder_name: str, skills: list[dict], mcps: list[dict]):
    """Downloads remote skills and configures MCPs locally for the workspace."""
    harness_dir = os.path.join(target_dir, harness_folder_name)
    
    # Guarantee superpowers is installed
    has_superpowers = any(s.get('name') == 'using-superpowers' for s in skills)
    if not has_superpowers:
        skills.append({
            "name": "using-superpowers",
            "url": "https://raw.githubusercontent.com/obra/superpowers/main/skills/using-superpowers/SKILL.md"
        })
    
    # Install Skills
    if skills:
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/integration/test_minting_engine.py::test_install_workspace_tools_guarantees_superpowers -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add harness/minting_engine.py tests/integration/test_minting_engine.py
git commit -m "feat: guarantee using-superpowers skill installation in workspace"
```

### Task 3: Fix Tool Installation Pathing Bug

**Files:**
- Modify: `harness/cli.py`

- [ ] **Step 1: Write minimal implementation**

In `harness/cli.py`, the `install_workspace_tools` is called with `args.project_path`. It should be called with `args.project_path` as the `target_dir`, and `harness_folder` as the second argument, which aligns with the signature `def install_workspace_tools(target_dir: str, harness_folder_name: str, skills: list[dict], mcps: list[dict]):`.

Wait, let's look at `install_workspace_tools`.
```python
def install_workspace_tools(target_dir: str, harness_folder_name: str, skills: list[dict], mcps: list[dict]):
    harness_dir = os.path.join(target_dir, harness_folder_name)
```
If `target_dir` is passed as `args.project_path` (e.g. `/path/to/project`), then `harness_dir` becomes `/path/to/project/.gemini`. This pathing is actually correct within `install_workspace_tools`. 

The bug is that the path inside `skills.json` might be written incorrectly relative to the CLI execution rather than the workspace root, OR `mint_workspace` has already been called.

Wait, `mint_workspace` is called with `target_dir` (which is `os.path.join(args.project_path, harness_folder)`).
```python
target_dir = os.path.join(args.project_path, harness_folder)
mint_workspace(target_dir, ...)
```

Then `install_workspace_tools` is called:
```python
install_workspace_tools(args.project_path, harness_folder, skills_to_install, mcps_to_install)
```
Inside `install_workspace_tools`:
```python
harness_dir = os.path.join(target_dir, harness_folder_name)
```
This means `harness_dir = os.path.join(args.project_path, harness_folder)` which equals `target_dir`.

So the path is actually correct! The reason skills aren't installed is because `parse_tool_checklists` failed to extract any skills because the markdown was rendered as `- [ ] No skills recommended`. And since no skills were in the list, `skills` was empty, and nothing was installed.

By adding `using-superpowers` unconditionally in Task 2, and expanding the registry in Task 1, we ensure skills *are* installed. No change is needed to `cli.py` pathing. I will drop this task and consider the plan complete.

- [ ] **Step 2: Run all tests to ensure no regressions**

Run: `PYTHONPATH=. pytest`
Expected: PASS

- [ ] **Step 3: Commit**

None required.
