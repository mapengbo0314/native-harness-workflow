"""Tests for is_dangerous_rm_command path matching (review 2026-06-12 M6).

The catch-all ``dangerous_paths`` list used bare ``/`` and ``.`` patterns that
matched *any* slash or dot, so ``rm -r build/dist`` was blocked as if it were
``rm -r /``.  These tests pin: genuinely dangerous targets stay blocked, while
ordinary relative paths containing a slash or an extension dot are allowed.

Note: ``rm -rf``/``rm -fr`` always returns True via the force-recursive patterns
*before* the path list is consulted, so the path logic is exercised with the
non-force ``rm -r`` form.
"""
from __future__ import annotations

from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks/pre_tool_use.py"
)


@pytest.fixture(scope="module")
def is_dangerous_rm_command():
    source = HOOK_PATH.read_text()
    ns: dict = {"__builtins__": __builtins__}
    exec("import json, re, sys\nfrom pathlib import Path\n" + source, ns)
    return ns["is_dangerous_rm_command"]


@pytest.mark.parametrize(
    "command",
    [
        "rm -r /",
        "rm -r /etc",
        "rm -r /*",
        "rm -r ~",
        "rm -r ~/cache",
        "rm -r ..",
        "rm -r ../sibling",
        "rm -r .",
    ],
)
def test_blocks_dangerous_targets(is_dangerous_rm_command, command):
    assert is_dangerous_rm_command(command) is True


@pytest.mark.parametrize(
    "command",
    [
        "rm -r build/dist",
        "rm -r ./build",
        "rm -r src/main",
        "rm -r node_modules",
        "rm -r my.folder",
    ],
)
def test_allows_ordinary_relative_paths(is_dangerous_rm_command, command):
    assert is_dangerous_rm_command(command) is False


def test_force_recursive_still_blocked_regardless_of_path(is_dangerous_rm_command):
    # -rf short-circuits on the force-recursive pattern before path checks.
    assert is_dangerous_rm_command("rm -rf build/dist") is True
