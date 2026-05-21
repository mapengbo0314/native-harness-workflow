# Omni-Compatible Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the CLI and Minting Engine to remove platform-specific prompts and generate a universal, omni-compatible workspace that works with Gemini CLI, Claude Code, Cursor, and Copilot simultaneously.

**Architecture:** We are moving from a "branching" initialization model to an "additive" model. Instead of picking one platform, we will unconditionally generate pointers for all of them and use a standardized `.agents/` directory for the core brain.

**Tech Stack:** Python, Bash.

---

### Task 1: Refactor CLI to Remove Platform Selection

**Files:**
- Modify: `harness/cli.py`

- [x] **Step 1: Remove the platform choice prompt**
Remove the "Platform Selection" print statements and the `platform_choice` input logic (lines 84-93).

- [x] **Step 2: Standardize the target directory**
Remove the conditional logic that sets `harness_folder` based on `platform_choice` (lines 98-99). Always set `harness_folder = ".agents"`.

- [x] **Step 3: Update the `mint_workspace` call**
Remove `platform_choice` from the call to `mint_workspace`.

- [x] **Step 4: Verify the CLI runs without interruption**
Run: `python3 -m harness.cli init --project-path . --llm gemini --ddd` (with dummy values)
Expected: No platform selection menu appears.

- [x] **Step 5: Commit**
```bash
git add harness/cli.py
git commit -m "refactor: remove platform selection prompt from CLI"
```

### Task 2: Refactor Minting Engine Signature & Directory Logic

**Files:**
- Modify: `harness/minting_engine.py`

- [x] **Step 1: Remove `platform_choice` from the signature**
Update `def mint_workspace(...)` to remove the `platform_choice` parameter.

- [x] **Step 2: Remove platform name logic**
Remove the `if/elif` block (lines 80-92) that sets `platform_name` and `CodeGraph_init_flag`.

- [x] **Step 3: Update `setup_harness.sh` header**
Change the header to: `echo "=== Setting up Omni-Compatible Agentic Harness Prerequisites ==="`

- [x] **Step 4: Commit**
```bash
git add harness/minting_engine.py
git commit -m "refactor: standardize minting engine signature and setup header"
```

### Task 3: Implement Unconditional Omni-Pointer Generation

**Files:**
- Modify: `harness/minting_engine.py`

- [x] **Step 1: Replace single-platform pointer logic with a loop**
Find the block (lines 185-201) that writes the `rules_file`. Replace it with logic that writes to all platforms.

```python
    # Generate Platform Rules Pointers IN THE ROOT DIRECTORY
    pointer_content = """# Agentic Harness
    
Please read `AGENTS.md` for core repository instructions and routing rules.
"""
    # Define all pointer files
    pointer_files = [
        "GEMINI.md",
        "CLAUDE.md",
        ".cursorrules"
    ]
    
    for rules_file in pointer_files:
        with open(project_root / rules_file, "w") as f:
            f.write(pointer_content)
            
    # Special case for Copilot (in .github/)
    copilot_dir = project_root / ".github"
    copilot_dir.mkdir(exist_ok=True)
    with open(copilot_dir / "copilot-instructions.md", "w") as f:
        f.write(pointer_content)
```

- [x] **Step 2: Verify all pointers are created**
Run a test minting and check the root directory.
Expected: `GEMINI.md`, `CLAUDE.md`, `.cursorrules`, and `.github/copilot-instructions.md` all exist.

- [x] **Step 3: Commit**
```bash
git add harness/minting_engine.py
git commit -m "feat: implement unconditional omni-pointer generation"
```

### Task 4: Implement Unconditional MCP and Skill Pointers

**Files:**
- Modify: `harness/minting_engine.py`

- [ ] **Step 1: Make Cursor MCP generation unconditional**
Remove the `if platform_choice == "4":` guard around the Cursor `mcp.json` generation (lines 212-217). Always generate it.

- [ ] **Step 2: Update `setup_harness.sh` to install all available platform extensions**
Refactor the setup script content (lines 101-137) to use independent `if command -v` blocks instead of choosing just one. (Note: Much of this is already independent, ensure they all run if the CLI is found).

- [ ] **Step 3: Verify mcp.json in both locations**
Check root `mcp.json` and `.cursor/mcp.json`.

- [ ] **Step 4: Commit**
```bash
git add harness/minting_engine.py
git commit -m "feat: implement universal MCP and setup logic"
```
