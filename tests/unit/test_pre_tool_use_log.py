"""C4 (review 2026-06-12): the pre_tool_use tool-call log must append in O(1)
and stay bounded, instead of read-all/rewrite-all of a growing JSON array.

We pin: one JSON line appended per call, and size-based rotation to `<name>.1`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks/pre_tool_use.py"
)


def _load_hook_ns() -> dict:
    source = HOOK_PATH.read_text()
    ns: dict = {"__builtins__": __builtins__}
    exec("import json, re, sys\nfrom pathlib import Path\n" + source, ns)
    return ns


@pytest.fixture(scope="module")
def ns():
    return _load_hook_ns()


def test_append_writes_one_jsonl_line_per_call(ns, tmp_path):
    log_path = tmp_path / "pre_tool_use.jsonl"
    append = ns["_append_tool_log"]

    for i in range(5):
        append(log_path, {"tool_name": "Bash", "i": i})

    lines = log_path.read_text().splitlines()
    assert len(lines) == 5
    # Each line is an independently parseable record (true JSONL).
    assert [json.loads(line)["i"] for line in lines] == [0, 1, 2, 3, 4]


def test_append_rotates_when_over_size_cap(ns, tmp_path):
    log_path = tmp_path / "pre_tool_use.jsonl"
    append = ns["_append_tool_log"]

    # Tiny cap so the second write triggers rotation.
    append(log_path, {"payload": "x" * 200}, max_bytes=50)
    first_inode_content = log_path.read_text()
    append(log_path, {"payload": "y"}, max_bytes=50)

    rotated = tmp_path / "pre_tool_use.jsonl.1"
    assert rotated.exists(), "expected rotated file"
    assert first_inode_content in rotated.read_text()
    # Live file restarted with just the newest record.
    assert log_path.read_text().splitlines() == [json.dumps({"payload": "y"})]
