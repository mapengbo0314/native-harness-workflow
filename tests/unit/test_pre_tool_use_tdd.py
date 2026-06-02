"""Tests for TDD enforcement logic in pre_tool_use hook.

Extracts only the pure logic functions via exec() to avoid module-level
side effects (hook_common imports that aren't available in test context).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_PATH = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks/pre_tool_use.py"
)


def _load_tdd_functions():
    """Extract pure TDD helper functions from the hook source."""
    source = HOOK_PATH.read_text()
    ns: dict = {}
    # Provide minimal stubs so exec doesn't fail on imports
    ns["__builtins__"] = __builtins__
    exec(
        "import json, re, sys\nfrom pathlib import Path\n" + source,
        ns,
    )
    return ns


@pytest.fixture(scope="module")
def ns():
    return _load_tdd_functions()


# ---------------------------------------------------------------------------
# _is_test_file
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,expected", [
    ("tests/test_auth.py", True),
    ("tests/test_data_table.py", True),
    ("src/test_utils.py", True),        # starts with test_
    ("src/auth_test.py", True),         # ends with _test.py
    ("src/auth.py", False),
    ("src/data_table.py", False),
    ("conftest.py", False),
    ("setup.py", False),
])
def test_is_test_file(ns, path, expected):
    assert ns["_is_test_file"](path) == expected, f"_is_test_file({path!r}) should be {expected}"


# ---------------------------------------------------------------------------
# _is_source_write
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool,file_path,expect_blocked", [
    ("Write", "src/auth.py", True),
    ("Edit", "src/data_table.py", True),
    ("MultiEdit", "src/utils.py", True),
    ("Write", "tests/test_auth.py", False),      # test file — not a source write
    ("Write", "src/auth.py", True),
    ("Read", "src/auth.py", False),              # read is not a write
    ("Bash", "src/auth.py", False),              # bash is not a file write
    ("Write", "CLAUDE.md", False),               # not .py
    ("Write", "config.json", False),             # not .py
])
def test_is_source_write(ns, tool, file_path, expect_blocked):
    result = ns["_is_source_write"](tool, {"file_path": file_path})
    if expect_blocked:
        assert result == file_path
    else:
        assert result is None


# ---------------------------------------------------------------------------
# _check_tdd  (full integration of the gate logic)
# ---------------------------------------------------------------------------

def test_tdd_blocks_source_write_before_test(ns, tmp_path):
    """First write to a source file with no test written → blocked."""
    session_id = "test-session-001"
    with patch.object(Path, "exists", return_value=False):
        result = ns["_check_tdd"]("Edit", {"file_path": "src/auth.py"}, session_id, tmp_path)
    assert result is not None
    assert "test" in result.lower()


def test_tdd_allows_test_file_write_always(ns, tmp_path):
    """Writing a test file is always allowed (this is the RED phase)."""
    session_id = "test-session-002"
    result = ns["_check_tdd"]("Write", {"file_path": "tests/test_auth.py"}, session_id, tmp_path)
    assert result is None


def test_tdd_allows_source_write_after_test_written(ns, tmp_path):
    """Source write is allowed once a test file has been written in session."""
    session_id = "test-session-003"
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / f"tdd_{session_id}.json").write_text(json.dumps({"test_written": True}))

    result = ns["_check_tdd"]("Edit", {"file_path": "src/auth.py"}, session_id, tmp_path)
    assert result is None


def test_tdd_writing_test_marks_state(ns, tmp_path):
    """Writing a test file creates the tdd state marker."""
    session_id = "test-session-004"
    # Write a test file — should mark state
    ns["_check_tdd"]("Write", {"file_path": "tests/test_auth.py"}, session_id, tmp_path)
    # Now a source write should be allowed
    result = ns["_check_tdd"]("Edit", {"file_path": "src/auth.py"}, session_id, tmp_path)
    assert result is None


def test_tdd_allows_non_python_source_write(ns, tmp_path):
    """Non-Python source files (JS, YAML, etc.) are not gated."""
    session_id = "test-session-005"
    result = ns["_check_tdd"]("Write", {"file_path": "src/config.yaml"}, session_id, tmp_path)
    assert result is None
