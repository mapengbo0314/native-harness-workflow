"""Phase 5 (F2 ECC port, R5): deterministic dispatch-budget backstop.

A budget in a dispatch prompt is a directive an agent may ignore (the observed
194k-token run was exactly that).  Before each Tier-2 dispatch the
adversary-pipeline skill writes a budget sidecar `state/budget_<session>.json`;
`pre_tool_use.py` increments its counters per tool call / file read and
hard-blocks past the limit with a summarize-and-finish message — the same
deterministic layer as the TDD and search-first gates.

Covers:
  - no sidecar ⇒ passthrough (zero cost to normal sessions)
  - counter increments per tool call, persisted to the sidecar
  - file-read counter increments only on read tools
  - block past max_tool_calls / max_file_reads with summarize-and-finish text
  - corrupt sidecar ⇒ fail-open passthrough
  - per-session isolation (one session's budget never throttles another)
  - e2e: exit 2 / gemini deny JSON when over budget
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks"
)
PRE_TOOL_USE = HOOKS_DIR / "pre_tool_use.py"


@pytest.fixture(scope="module")
def pre_tool_use():
    sys.path.insert(0, str(HOOKS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("pre_tool_use_budget_test", PRE_TOOL_USE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(HOOKS_DIR))


@pytest.fixture
def plugin_root(tmp_path):
    (tmp_path / "state").mkdir()
    return tmp_path


def _sidecar(plugin_root: Path, session_id: str) -> Path:
    return plugin_root / "state" / f"budget_{session_id}.json"


def _write_budget(plugin_root: Path, session_id: str, **overrides) -> Path:
    data = {"max_tool_calls": 30, "max_file_reads": 12, "tool_calls": 0, "file_reads": 0}
    data.update(overrides)
    f = _sidecar(plugin_root, session_id)
    f.write_text(json.dumps(data))
    return f


class TestBudgetPassthrough:
    def test_no_sidecar_passthrough(self, pre_tool_use, plugin_root):
        assert pre_tool_use._check_budget("Bash", {"command": "ls"}, "s1", plugin_root) is None

    def test_corrupt_sidecar_fails_open(self, pre_tool_use, plugin_root):
        _sidecar(plugin_root, "s1").write_text("{not json")
        assert pre_tool_use._check_budget("Bash", {"command": "ls"}, "s1", plugin_root) is None


class TestCounters:
    def test_tool_call_increments_and_persists(self, pre_tool_use, plugin_root):
        _write_budget(plugin_root, "s1")
        assert pre_tool_use._check_budget("Bash", {"command": "ls"}, "s1", plugin_root) is None
        data = json.loads(_sidecar(plugin_root, "s1").read_text())
        assert data["tool_calls"] == 1
        assert data["file_reads"] == 0

    def test_read_tool_increments_both_counters(self, pre_tool_use, plugin_root):
        _write_budget(plugin_root, "s1")
        pre_tool_use._check_budget("Read", {"file_path": "src/foo.py"}, "s1", plugin_root)
        data = json.loads(_sidecar(plugin_root, "s1").read_text())
        assert data["tool_calls"] == 1
        assert data["file_reads"] == 1

    def test_gemini_read_tool_counts_as_file_read(self, pre_tool_use, plugin_root):
        _write_budget(plugin_root, "s1")
        pre_tool_use._check_budget("read_file", {"file_path": "src/foo.py"}, "s1", plugin_root)
        data = json.loads(_sidecar(plugin_root, "s1").read_text())
        assert data["file_reads"] == 1


class TestBlocking:
    def test_blocks_past_max_tool_calls(self, pre_tool_use, plugin_root):
        _write_budget(plugin_root, "s1", max_tool_calls=2)
        assert pre_tool_use._check_budget("Bash", {"command": "a"}, "s1", plugin_root) is None
        assert pre_tool_use._check_budget("Bash", {"command": "b"}, "s1", plugin_root) is None
        msg = pre_tool_use._check_budget("Bash", {"command": "c"}, "s1", plugin_root)
        assert msg is not None
        assert "summarize" in msg.lower()
        assert "budget" in msg.lower()

    def test_blocks_past_max_file_reads(self, pre_tool_use, plugin_root):
        _write_budget(plugin_root, "s1", max_file_reads=1, max_tool_calls=100)
        assert pre_tool_use._check_budget("Read", {"file_path": "a.py"}, "s1", plugin_root) is None
        msg = pre_tool_use._check_budget("Read", {"file_path": "b.py"}, "s1", plugin_root)
        assert msg is not None
        assert "summarize" in msg.lower()

    def test_non_read_tools_unaffected_by_file_read_limit(self, pre_tool_use, plugin_root):
        _write_budget(plugin_root, "s1", max_file_reads=0, max_tool_calls=100)
        assert pre_tool_use._check_budget("Bash", {"command": "ls"}, "s1", plugin_root) is None

    def test_missing_limit_keys_use_defaults(self, pre_tool_use, plugin_root):
        """Sidecar with only counters ⇒ defaults 30/12 apply, not a crash."""
        _sidecar(plugin_root, "s1").write_text(json.dumps({"tool_calls": 29, "file_reads": 0}))
        assert pre_tool_use._check_budget("Bash", {"command": "a"}, "s1", plugin_root) is None
        msg = pre_tool_use._check_budget("Bash", {"command": "b"}, "s1", plugin_root)
        assert msg is not None


class TestBlockedCallsDontConsume:
    """Phase 6a hardening (review finding #5): check-before-write — a call
    the wall rejects must not persist an increment, and a call another gate
    rejects must not consume budget at all."""

    def test_budget_blocked_call_not_persisted(self, pre_tool_use, plugin_root):
        _write_budget(plugin_root, "s1", max_tool_calls=1)
        assert pre_tool_use._check_budget("Bash", {"command": "a"}, "s1", plugin_root) is None
        assert pre_tool_use._check_budget("Bash", {"command": "b"}, "s1", plugin_root) is not None
        data = json.loads(_sidecar(plugin_root, "s1").read_text())
        assert data["tool_calls"] == 1, "rejected attempt must not be persisted"

    def test_no_tmp_residue_after_write(self, pre_tool_use, plugin_root):
        _write_budget(plugin_root, "s1")
        pre_tool_use._check_budget("Bash", {"command": "a"}, "s1", plugin_root)
        assert not list((plugin_root / "state").glob("budget_*.tmp")), "atomic write must clean up"

    def test_tdd_blocked_call_does_not_consume_budget(self, plugin_root):
        """e2e: a source write rejected by the TDD gate never reaches the
        budget counter (budget check runs after the workflow gates)."""
        _write_budget(plugin_root, "e2e", max_tool_calls=10)
        p = _run_hook(plugin_root, {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}})
        assert p.returncode == 2
        assert "TDD" in p.stderr
        data = json.loads(_sidecar(plugin_root, "e2e").read_text())
        assert data["tool_calls"] == 0, "TDD-blocked call must not consume budget"


class TestSessionIsolation:
    def test_one_sessions_budget_never_throttles_another(self, pre_tool_use, plugin_root):
        _write_budget(plugin_root, "s1", max_tool_calls=0)
        assert pre_tool_use._check_budget("Bash", {"command": "x"}, "s1", plugin_root) is not None
        assert pre_tool_use._check_budget("Bash", {"command": "x"}, "s2", plugin_root) is None


# ---------------------------------------------------------------------------
# End-to-end: hook process wiring
# ---------------------------------------------------------------------------


def _run_hook(plugin_root: Path, payload: dict):
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env["HARNESS_SESSION_ID"] = "e2e"
    return subprocess.run(
        [sys.executable, str(PRE_TOOL_USE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestHookProcessWiring:
    def test_over_budget_exits_2(self, plugin_root):
        _write_budget(plugin_root, "e2e", max_tool_calls=0)
        p = _run_hook(plugin_root, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert p.returncode == 2
        assert "budget" in p.stderr.lower()

    def test_over_budget_gemini_deny_json(self, plugin_root):
        _write_budget(plugin_root, "e2e", max_tool_calls=0)
        p = _run_hook(plugin_root, {
            "tool_name": "run_shell_command",
            "tool_input": {"command": "ls"},
            "hook_event_name": "PreToolUse",
        })
        assert p.returncode == 0
        out = json.loads(p.stdout.splitlines()[-1])
        assert out.get("decision") == "deny"

    def test_no_sidecar_passthrough_e2e(self, plugin_root):
        p = _run_hook(plugin_root, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert p.returncode == 0


# ---------------------------------------------------------------------------
# Stale-sidecar hygiene: retention prune covers budget sidecars
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hook_common():
    spec = importlib.util.spec_from_file_location(
        "hook_common_budget_test", HOOKS_DIR / "hook_common.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestStaleSidecarPrune:
    def test_old_budget_sidecar_pruned(self, hook_common, plugin_root):
        """Design: 'stale sidecars pruned by the Phase 2 retention helper' —
        a crashed Tier-2 session must not leave a permanent budget file."""
        import time
        f = _write_budget(plugin_root, "old")
        ancient = time.time() - 60 * 60 * 24 * 40  # 40 days
        os.utime(f, (ancient, ancient))
        hook_common.prune_old_session_files(plugin_root)
        assert not f.exists()

    def test_recent_budget_sidecar_kept(self, hook_common, plugin_root):
        f = _write_budget(plugin_root, "fresh")
        hook_common.prune_old_session_files(plugin_root)
        assert f.exists()

    def test_old_tdd_sidecar_pruned(self, hook_common, plugin_root):
        """Phase 6a Group 2: tdd_<session>.json joins retention — a recycled
        session id must not inherit a stale test_written flag (TDD-gate
        bypass), and state/ must not accumulate one file per session forever."""
        import time
        f = plugin_root / "state" / "tdd_old.json"
        f.write_text(json.dumps({"test_written": True}))
        ancient = time.time() - 60 * 60 * 24 * 40
        os.utime(f, (ancient, ancient))
        hook_common.prune_old_session_files(plugin_root)
        assert not f.exists()

    def test_recent_tdd_sidecar_kept(self, hook_common, plugin_root):
        f = plugin_root / "state" / "tdd_fresh.json"
        f.write_text(json.dumps({"test_written": True}))
        hook_common.prune_old_session_files(plugin_root)
        assert f.exists()
