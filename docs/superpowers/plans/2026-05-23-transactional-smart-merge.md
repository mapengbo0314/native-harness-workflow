# Transactional Smart Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement safe, deterministic harness minting via atomic staging and smart merging of Markdown and JSON/YAML files.

**Architecture:** 
- Stage all rendering in `.harness_tmp`.
- Implement `merge_markdown`, `merge_structured`, and `handle_code_conflicts` in `src/harness/minting_engine.py`.
- Update `src/harness/cli.py` to use these functions and handle the 'Atomic Swap' (backup existing, move tmp to target).

**Tech Stack:** Python (Pathlib, shutil, json, re, difflib, yaml)

---

## 1. Merging Logic Implementation

### [ ] Step 1.1: Unit Tests for Merging
Create `tests/unit/test_smart_merge.py` with cases for MD sections, JSON deep merge, and YAML deep merge.

**Failing Test Example:**
```python
import pytest
from harness.minting_engine import merge_markdown, merge_structured

def test_merge_markdown_sections():
    old_md = "# Header 1\nOld content\n# Header 2\nOld Header 2 content"
    new_md = "# Header 1\nNew content\n# Header 3\nNew Header 3 content"
    merged = merge_markdown(old_md, new_md)
    assert "# Header 1\nNew content" in merged
    assert "# Header 2\nOld Header 2 content" in merged
    assert "# Header 3\nNew Header 3 content" in merged

def test_merge_structured_json():
    old_json = '{"a": 1, "b": {"c": 2}}'
    new_json = '{"b": {"d": 3}, "e": 4}'
    merged = merge_structured(old_json, new_json, format="json")
    import json
    data = json.loads(merged)
    assert data["a"] == 1
    assert data["b"]["c"] == 2
    assert data["b"]["d"] == 3
    assert data["e"] == 4
```

### [ ] Step 1.2: Implement `merge_markdown` in `src/harness/minting_engine.py`
Implement section-aware markdown merging using regex to split by headers.

**Implementation Hint:**
```python
def merge_markdown(old_content: str, new_content: str) -> str:
    # 1. Parse sections: map of header -> full content (header + body)
    # 2. Update old map with new map entries
    # 3. Reconstruct string, preserving new order and appending missing old sections
    ...
```

### [ ] Step 1.3: Implement `merge_structured` in `src/harness/minting_engine.py`
Implement recursive deep merge for JSON/YAML.

**Implementation Hint:**
```python
def deep_merge(dict1, dict2):
    for key, value in dict2.items():
        if key in dict1 and isinstance(dict1[key], dict) and isinstance(value, dict):
            deep_merge(dict1[key], value)
        elif key in dict1 and isinstance(dict1[key], list) and isinstance(value, list):
            # Union of lists for simple types
            try:
                dict1[key] = list(set(dict1[key]) | set(value))
            except TypeError:
                dict1[key].extend([v for v in value if v not in dict1[key]])
        else:
            dict1[key] = value
    return dict1
```

### [ ] Step 1.4: Implement `handle_code_conflicts` in `src/harness/minting_engine.py`
Implement interactive conflict resolution with `difflib`. Skip in `HARNESS_HEADLESS` mode.

### [ ] Step 1.5: Implement `perform_smart_merge` in `src/harness/minting_engine.py`
Implement the walker that traverses the staged directory and merges files with the existing harness.

```python
def perform_smart_merge(existing_path: Path, new_path: Path):
    """Walks through new_path and merges files into it from existing_path if they exist."""
    ...
```

## 2. CLI Refactoring for Atomic Swap

### [ ] Step 2.1: Atomic Swap Orchestration in `src/harness/cli.py`
Wrap the minting calls in a temporary directory logic. Create `.harness_tmp` inside the project root to ensure same-filesystem move operations.

**Implementation Logic in `main()`:**
```python
    target_harness_dir = Path(args.project_path) / harness_folder
    temp_harness_dir = Path(args.project_path) / ".harness_tmp"
    
    if temp_harness_dir.exists():
        shutil.rmtree(temp_harness_dir)
    temp_harness_dir.mkdir(parents=True)

    # 1. Mint into temp folder
    mint_workspace(str(temp_harness_dir), ...)
    install_workspace_tools(args.project_path, ".harness_tmp", ...)
    # ... other minting functions targeting .harness_tmp ...

    # 2. Perform Smart Merge if existing harness exists
    if target_harness_dir.exists():
        perform_smart_merge(target_harness_dir, temp_harness_dir)
        
        # 3. Backup existing
        backup_name = f"{harness_folder}.backup.{int(time.time())}"
        shutil.move(target_harness_dir, Path(args.project_path) / backup_name)
    
    # 4. Swap
    shutil.move(temp_harness_dir, target_harness_dir)
```

### [ ] Step 2.2: Handle Root Pointer Files
Ensure `GEMINI.md`, `CLAUDE.md`, and `.cursorrules` are also merged if they already exist in the project root.

## 3. Verification & Polish

### [ ] Step 3.1: Integration Test
Create `tests/e2e/test_transactional_minting.py` that:
1. Mints a harness.
2. Modifies a section in `orchestrator.md`.
3. Adds a custom key to `mcp.json`.
4. Re-mints the harness.
5. Verifies that modifications are preserved and new boilerplate updates are applied.

### [ ] Step 3.2: Verification of Headless Mode
Ensure `HARNESS_HEADLESS=1` correctly defaults to using 'New' content for code files and 'Merge' for MD/JSON without blocking.

---

## Verification Strategy
- **Unit Tests**: `pytest tests/unit/test_smart_merge.py`
- **E2E Tests**: `pytest tests/e2e/test_transactional_minting.py`
- **Manual**: Run `harness-wf init` twice on a project and verify `.backup.*` creation and section preservation.

## Sphinch Marks
- [ ] `merge_markdown` correctly merges sections from two strings.
- [ ] `merge_structured` correctly deep-merges two JSON/YAML dicts.
- [ ] `mint_workspace` renders into a temporary directory first.
- [ ] `cli.py` handles the atomic swap and backups.
- [ ] Headless mode bypasses interactive prompts and uses defaults/backups.

---
**Instruction for Orchestrator:** Delegate execution to the `@implementer` agent using the `harness-subagent-driven-development` skill.
