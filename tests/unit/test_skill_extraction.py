"""Unit and TDD tests for Phase 3: F1 Continuous Learning skill extraction."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add hooks directory to path for import
HOOKS_DIR = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks"
)
sys.path.insert(0, str(HOOKS_DIR))


@pytest.fixture
def temp_home(tmp_path):
    """Temporary home directory to isolate learned skills storage."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    return home_dir


@pytest.fixture
def plugin_root(tmp_path):
    """Fresh plugin root with state/ and scripts/ directories."""
    root = tmp_path / "plugin"
    (root / "state").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    return root


def get_repo_hash(project_root: Path) -> str:
    """Helper to compute deterministic repo-hash (matching the implementation)."""
    return hashlib.sha256(str(project_root.resolve()).encode("utf-8")).hexdigest()[:16]


def test_skill_extraction_success(plugin_root, temp_home, monkeypatch):
    """Verify standard extraction from session transcript to SKILL.md.

    Should parse LLM output, format frontmatter, verify confidence & slug,
    write outside the repo, and clean up inputs.
    """
    # 1. Setup paths
    workspace_root = plugin_root.parent / "workspace"
    workspace_root.mkdir()

    repo_hash = get_repo_hash(workspace_root)
    learned_dir = temp_home / ".local/share/harness-wf/projects" / repo_hash / "learned"

    # Mock home directory via env override for extraction script
    monkeypatch.setenv("HARNESS_HOME_OVERRIDE", str(temp_home))

    # 2. Write mock input transcript (>= 10 turns)
    input_payload = {
        "workspace_root": str(workspace_root),
        "transcript": [{"role": "user", "text": f"turn {i}"} for i in range(12)]
    }
    input_file = plugin_root / "state" / "learning_input_test_session.json"
    input_file.write_text(json.dumps(input_payload), encoding="utf-8")

    # 3. Write mock lockfile
    lockfile = plugin_root / "state" / "learning.lock"
    lockfile.write_text("locked", encoding="utf-8")

    # 4. Mock LLM Response
    llm_response = {
        "slug": "custom-sql-optimizations",
        "title": "Custom SQL Optimizations",
        "description": "Guidelines for indexing highly-queried Postgres tables dynamically.",
        "confidence": 0.85,
        "stack": ["postgres", "sql"],
        "business": ["database scaling"],
        "content": "## Optimizing Custom SQL Queries\nAlways analyze with EXPLAIN ANALYZE."
    }

    # Run the script via python, mocking the LLM call
    extract_script = HOOKS_DIR.parent / "scripts" / "extract_skills.py"

    # We'll use sys.executable and subprocess, but to mock LLM client easily,
    # we can import and execute the script's main or main-like function directly.
    # Let's import the script module dynamically
    sys.path.insert(0, str(HOOKS_DIR.parent / "scripts"))

    with patch("harness.runtime.llm_client.query_llm") as mock_query_llm:
        mock_query_llm.return_value = json.dumps(llm_response)

        # Import and run
        import extract_skills

        # Ensure reload if needed or run directly
        extract_skills.extract_and_save(
            plugin_root=plugin_root,
            input_file=input_file,
            session_id="test_session"
        )

    # 5. Verify SKILL.md creation and shape
    skill_file = learned_dir / "custom-sql-optimizations" / "SKILL.md"
    assert skill_file.exists()

    content = skill_file.read_text(encoding="utf-8")

    # Frontmatter assertions
    assert content.startswith("---")
    assert "name: custom-sql-optimizations" in content
    assert "description: Guidelines for indexing highly-queried Postgres tables dynamically." in content
    assert "confidence: 0.85" in content
    assert "stack: ['postgres', 'sql']" in content or "stack:\n  - postgres" in content or "postgres" in content
    assert "business: ['database scaling']" in content or "database scaling" in content
    assert "---" in content[3:]  # End of frontmatter

    # Content assertions
    assert "## Optimizing Custom SQL Queries" in content
    assert "Always analyze with EXPLAIN ANALYZE." in content

    # 6. Verify that it was NOT written inside the repository
    assert not (plugin_root / "skills").exists()
    assert not (workspace_root / "skills").exists()

    # 7. Verify cleanup (input file and lockfile deleted)
    assert not input_file.exists()
    assert not lockfile.exists()


def test_skill_extraction_dedup_behavior(plugin_root, temp_home, monkeypatch):
    """Verify that learning dedups against existing skills in the out-of-repo dir."""
    workspace_root = plugin_root.parent / "workspace"
    workspace_root.mkdir(exist_ok=True)

    repo_hash = get_repo_hash(workspace_root)
    learned_dir = temp_home / ".local/share/harness-wf/projects" / repo_hash / "learned"

    # Create an existing skill with a lower confidence
    existing_skill_dir = learned_dir / "custom-sql-optimizations"
    existing_skill_dir.mkdir(parents=True)
    existing_skill_file = existing_skill_dir / "SKILL.md"
    existing_skill_file.write_text(
        "---\nname: custom-sql-optimizations\nconfidence: 0.5\n---\nOld content",
        encoding="utf-8"
    )

    monkeypatch.setenv("HARNESS_HOME_OVERRIDE", str(temp_home))
    sys.path.insert(0, str(HOOKS_DIR.parent / "scripts"))

    # Case A: New skill has HIGHER confidence (0.85 > 0.50) -> Should overwrite
    input_payload = {
        "workspace_root": str(workspace_root),
        "transcript": [{"role": "user", "text": "turn"} for _ in range(10)]
    }
    input_file = plugin_root / "state" / "learning_input_session_a.json"
    input_file.write_text(json.dumps(input_payload), encoding="utf-8")

    # Set lockfile
    lockfile = plugin_root / "state" / "learning.lock"
    lockfile.write_text("locked", encoding="utf-8")

    llm_response = {
        "slug": "custom-sql-optimizations",
        "title": "Custom SQL Optimizations",
        "description": "High-confidence replacement.",
        "confidence": 0.85,
        "stack": ["postgres"],
        "business": ["scaling"],
        "content": "New high-confidence content"
    }

    with patch("harness.runtime.llm_client.query_llm") as mock_query_llm:
        mock_query_llm.return_value = json.dumps(llm_response)

        import extract_skills
        import importlib
        importlib.reload(extract_skills)

        extract_skills.extract_and_save(
            plugin_root=plugin_root,
            input_file=input_file,
            session_id="session_a"
        )

    # Should overwrite
    assert "New high-confidence content" in existing_skill_file.read_text(encoding="utf-8")
    assert not input_file.exists()
    assert not lockfile.exists()

    # Case B: New skill has LOWER confidence (0.40 < 0.85) -> Should NOT overwrite
    input_file_b = plugin_root / "state" / "learning_input_session_b.json"
    input_file_b.write_text(json.dumps(input_payload), encoding="utf-8")
    lockfile.write_text("locked", encoding="utf-8")

    llm_response_low = {
        "slug": "custom-sql-optimizations",
        "title": "Custom SQL Optimizations",
        "description": "Low-confidence attempt.",
        "confidence": 0.40,
        "stack": ["postgres"],
        "business": ["scaling"],
        "content": "Low-confidence content"
    }

    with patch("harness.runtime.llm_client.query_llm") as mock_query_llm:
        mock_query_llm.return_value = json.dumps(llm_response_low)

        importlib.reload(extract_skills)
        extract_skills.extract_and_save(
            plugin_root=plugin_root,
            input_file=input_file_b,
            session_id="session_b"
        )

    # Should NOT overwrite, should keep the old (0.85) content
    assert "New high-confidence content" in existing_skill_file.read_text(encoding="utf-8")
    assert "Low-confidence content" not in existing_skill_file.read_text(encoding="utf-8")
    assert not input_file_b.exists()
    assert not lockfile.exists()

def test_robust_frontmatter_parsing_with_comments_and_quotes():
    """Verify that frontmatter parsing handles trailing comments, surrounding quotes, and extra colons robustly."""
    import extract_skills
    
    # Test case 1: Trailing comments on float/confidence and strings, extra colons in value
    raw_md = """---
name: "my-awesome-skill" # some comment
description: "Use Postgres: dynamic indexing with EXPLAIN ANALYZE"
confidence: 0.85 # high confidence score
stack: ['postgres', 'sql'] # dev stack
---
Some content here"""
    
    fm = extract_skills.parse_frontmatter(raw_md)
    assert fm.get("name") == "my-awesome-skill"
    assert fm.get("description") == "Use Postgres: dynamic indexing with EXPLAIN ANALYZE"
    assert fm.get("confidence") == 0.85
    assert fm.get("stack") == ["postgres", "sql"]

    # Test case 2: Single and double quote stripping and whitespaces
    raw_md_quotes = """---
'name': 'single-quoted-name'
"description": "double-quoted-description"
confidence: '0.75' # comment with single quotes
---
Some content here"""

    fm_quotes = extract_skills.parse_frontmatter(raw_md_quotes)
    assert fm_quotes.get("name") == "single-quoted-name"
    assert fm_quotes.get("description") == "double-quoted-description"
    assert fm_quotes.get("confidence") == 0.75
