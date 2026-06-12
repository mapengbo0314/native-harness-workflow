"""Phase 6a (session identity repair): stable session identity across hooks
and skill-invoked scripts.

The defect: hooks resolve a stable fallback id (the CLI's pid via ppid) while
scripts launched from skills resolve a fresh ephemeral shell pid every call —
so set-phase / set-research-done / budget-arm writes land in stores the
enforcing hooks never read (observed live: 73171 → 80226 → 80490 in one
conversation).

Repair (risk-report M1 resolution order):
  HARNESS_SESSION_ID (explicit override)
  → input_json["session_id"] (platform truth)
  → CLAUDE_SESSION_ID / GEMINI_SESSION_ID
  → pointer file state/current_session (published by hooks)
  → ppid (last resort)

Also: /clear semantics — different payload ids never share a store; the
pointer file is exempt from retention pruning.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks"
)
SCRIPTS_DIR = HOOKS_DIR.parent / "scripts"
PRE_TOOL_USE = HOOKS_DIR / "pre_tool_use.py"
SESSION_PHASE = SCRIPTS_DIR / "session_phase.py"

_ID_ENV_VARS = ("HARNESS_SESSION_ID", "CLAUDE_SESSION_ID", "GEMINI_SESSION_ID")


@pytest.fixture
def hook_common(monkeypatch, tmp_path):
    """Fresh hook_common with a tmp plugin root and scrubbed id env."""
    for var in _ID_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(tmp_path))
    (tmp_path / "state").mkdir()
    spec = importlib.util.spec_from_file_location(
        "hook_common_identity_test", HOOKS_DIR / "hook_common.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._test_plugin_root = tmp_path
    return mod


# ---------------------------------------------------------------------------
# get_session_id resolution order (M1)
# ---------------------------------------------------------------------------


class TestResolutionOrder:
    def test_harness_env_override_wins_over_payload(self, hook_common, monkeypatch):
        monkeypatch.setenv("HARNESS_SESSION_ID", "override-id")
        assert hook_common.get_session_id({"session_id": "payload-id"}) == "override-id"

    def test_payload_wins_over_platform_env(self, hook_common, monkeypatch):
        monkeypatch.setenv("CLAUDE_SESSION_ID", "platform-id")
        assert hook_common.get_session_id({"session_id": "payload-id"}) == "payload-id"

    def test_platform_env_wins_over_pointer(self, hook_common, monkeypatch):
        monkeypatch.setenv("CLAUDE_SESSION_ID", "platform-id")
        hook_common.publish_session_pointer(hook_common._test_plugin_root, "pointer-id")
        assert hook_common.get_session_id() == "platform-id"

    def test_pointer_wins_over_ppid(self, hook_common):
        hook_common.publish_session_pointer(hook_common._test_plugin_root, "pointer-id")
        assert hook_common.get_session_id() == "pointer-id"

    def test_ppid_last_resort(self, hook_common):
        assert hook_common.get_session_id() == str(os.getppid())

    def test_empty_payload_id_ignored(self, hook_common):
        hook_common.publish_session_pointer(hook_common._test_plugin_root, "pointer-id")
        assert hook_common.get_session_id({"session_id": ""}) == "pointer-id"

    def test_no_payload_arg_backward_compatible(self, hook_common, monkeypatch):
        monkeypatch.setenv("HARNESS_SESSION_ID", "legacy")
        assert hook_common.get_session_id() == "legacy"


# ---------------------------------------------------------------------------
# publish_session_pointer
# ---------------------------------------------------------------------------


class TestPointer:
    def test_publish_and_read_back(self, hook_common):
        root = hook_common._test_plugin_root
        hook_common.publish_session_pointer(root, "abc-123")
        assert (root / "state" / "current_session").read_text(encoding="utf-8").strip() == "abc-123"

    def test_overwrite_last_writer_wins(self, hook_common):
        root = hook_common._test_plugin_root
        hook_common.publish_session_pointer(root, "first")
        hook_common.publish_session_pointer(root, "second")
        assert hook_common.get_session_id() == "second"

    def test_fail_open_on_bad_root(self, hook_common):
        # Must never raise — enforcement plumbing cannot break hooks.
        hook_common.publish_session_pointer("/nonexistent/path/xyz", "id")

    def test_pointer_exempt_from_pruning(self, hook_common):
        root = hook_common._test_plugin_root
        hook_common.publish_session_pointer(root, "keep-me")
        pointer = root / "state" / "current_session"
        ancient = time.time() - 60 * 60 * 24 * 60
        os.utime(pointer, (ancient, ancient))
        hook_common.prune_old_session_files(root)
        assert pointer.exists()


# ---------------------------------------------------------------------------
# Hooks thread the payload id + publish the pointer (e2e)
# ---------------------------------------------------------------------------


def _run_pre_tool_use(plugin_root: Path, payload: dict, extra_env: dict = None):
    env = {k: v for k, v in os.environ.items() if k not in _ID_ENV_VARS}
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(PRE_TOOL_USE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


@pytest.fixture
def plugin_root(tmp_path):
    (tmp_path / "state").mkdir(exist_ok=True)
    return tmp_path


class TestHookPayloadThreading:
    def test_hook_uses_payload_id_for_state(self, plugin_root):
        """A test-file write marks TDD state under the PAYLOAD session id."""
        p = _run_pre_tool_use(plugin_root, {
            "session_id": "conv-AAA",
            "tool_name": "Write",
            "tool_input": {"file_path": "tests/test_x.py"},
        })
        assert p.returncode == 0, p.stderr
        assert (plugin_root / "state" / "tdd_conv-AAA.json").exists()

    def test_hook_publishes_pointer(self, plugin_root):
        _run_pre_tool_use(plugin_root, {
            "session_id": "conv-BBB",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        })
        pointer = plugin_root / "state" / "current_session"
        assert pointer.exists()
        assert pointer.read_text(encoding="utf-8").strip() == "conv-BBB"

    def test_clear_simulation_no_shared_store(self, plugin_root):
        """/clear ⇒ new payload id ⇒ a fresh store; the old session's TDD
        mark must NOT leak into the new session."""
        _run_pre_tool_use(plugin_root, {
            "session_id": "before-clear",
            "tool_name": "Write",
            "tool_input": {"file_path": "tests/test_x.py"},
        })
        # New session attempts a source write WITHOUT having written a test:
        p = _run_pre_tool_use(plugin_root, {
            "session_id": "after-clear",
            "tool_name": "Edit",
            "tool_input": {"file_path": "src/foo.py"},
        })
        assert p.returncode == 2, "new session must not inherit old TDD state"
        assert "TDD" in p.stderr


# ---------------------------------------------------------------------------
# Scripts: --session flag, pointer fallback (the live-broken loop)
# ---------------------------------------------------------------------------


def _run_script(plugin_root: Path, *args, with_env_id: str = None):
    env = {k: v for k, v in os.environ.items() if k not in _ID_ENV_VARS}
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    if with_env_id:
        env["HARNESS_SESSION_ID"] = with_env_id
    return subprocess.run(
        [sys.executable, str(SESSION_PHASE), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


class TestScriptSessionResolution:
    def test_explicit_session_flag(self, hook_common, plugin_root):
        p = _run_script(plugin_root, "set-phase", "planning", "--session", "conv-XYZ")
        assert p.returncode == 0, p.stderr
        phase = hook_common.get_phase(plugin_root, "conv-XYZ")
        assert phase and phase["phase"] == "planning"

    def test_pointer_fallback_reaches_hook_store(self, hook_common, plugin_root):
        """The repaired live loop: hook publishes pointer → script with no
        flag and no env writes to the SAME store the hook reads."""
        _run_pre_tool_use(plugin_root, {
            "session_id": "conv-LIVE",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        })
        p = _run_script(plugin_root, "set-research-done", "--note", "via pointer")
        assert p.returncode == 0, p.stderr
        assert hook_common.get_research_done(plugin_root, "conv-LIVE")

    def test_session_flag_wins_over_pointer(self, hook_common, plugin_root):
        hook_common.publish_session_pointer(plugin_root, "pointer-id")
        _run_script(plugin_root, "set-phase", "tdd", "--session", "flag-id")
        assert hook_common.get_phase(plugin_root, "flag-id")
        assert hook_common.get_phase(plugin_root, "pointer-id") is None


# ---------------------------------------------------------------------------
# arm-budget / disarm-budget subcommands (replaces SKILL.md heredocs)
# ---------------------------------------------------------------------------


class TestBudgetSubcommands:
    def test_arm_budget_default_limits(self, plugin_root):
        p = _run_script(plugin_root, "arm-budget", "--session", "s1")
        assert p.returncode == 0, p.stderr
        data = json.loads((plugin_root / "state" / "budget_s1.json").read_text())
        assert data == {"max_tool_calls": 30, "max_file_reads": 12,
                        "tool_calls": 0, "file_reads": 0}

    def test_arm_budget_custom_limits(self, plugin_root):
        _run_script(plugin_root, "arm-budget", "--session", "s1",
                    "--max-tool-calls", "5", "--max-file-reads", "3")
        data = json.loads((plugin_root / "state" / "budget_s1.json").read_text())
        assert data["max_tool_calls"] == 5
        assert data["max_file_reads"] == 3

    def test_disarm_budget_removes_sidecar(self, plugin_root):
        _run_script(plugin_root, "arm-budget", "--session", "s1")
        p = _run_script(plugin_root, "disarm-budget", "--session", "s1")
        assert p.returncode == 0, p.stderr
        assert not (plugin_root / "state" / "budget_s1.json").exists()

    def test_disarm_when_absent_is_noop(self, plugin_root):
        p = _run_script(plugin_root, "disarm-budget", "--session", "never-armed")
        assert p.returncode == 0, p.stderr

    def test_armed_budget_binds_hook_with_same_payload_id(self, plugin_root):
        """The repaired Tier-2 wall: arm via script, hook with the matching
        payload id enforces it."""
        _run_script(plugin_root, "arm-budget", "--session", "conv-T2",
                    "--max-tool-calls", "0")
        p = _run_pre_tool_use(plugin_root, {
            "session_id": "conv-T2",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        })
        assert p.returncode == 2
        assert "budget" in p.stderr.lower()
