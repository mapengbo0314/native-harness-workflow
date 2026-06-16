"""Phase 3 (ECC feature port): SessionEnd hook and learning extraction tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import errno
import time
from pathlib import Path
import pytest

HOOKS_DIR = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks"
)

SESSION_END_HOOK = HOOKS_DIR / "session_end.py"


@pytest.fixture
def plugin_root(tmp_path):
    """A fresh plugin root with a state/ subdirectory."""
    (tmp_path / "state").mkdir()
    return tmp_path


def write_features(root: Path, data: dict) -> None:
    (root / "features.json").write_text(json.dumps(data, ensure_ascii=False))


def run_hook(hook_path: Path, input_payload: dict, env_overrides: dict | None = None, plugin_root: Path | None = None):
    """Run a hook subprocess and return the CompletedProcess."""
    p_root = str(plugin_root) if plugin_root else str(hook_path.parent.parent)
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": p_root,
        "GEMINI_PLUGIN_ROOT": p_root,
    }
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(input_payload),
        capture_output=True,
        text=True,
        env=env,
    )


def test_session_end_recursion_guard(plugin_root):
    """Verify that SessionEnd hook exits immediately when HARNESS_INTERNAL_LLM_CALL=1 is set."""
    write_features(plugin_root, {"hooks": {"session_end": {"learning_extraction": True}}})

    # Even with sufficient turns, recursion guard should skip extraction
    payload = {
        "workspace_root": str(plugin_root),
        "transcript": [{"role": "user", "text": "turn"} for _ in range(10)]
    }

    res = run_hook(SESSION_END_HOOK, payload, {"HARNESS_INTERNAL_LLM_CALL": "1"}, plugin_root=plugin_root)
    assert res.returncode == 0
    # No lockfile should be created
    assert not (plugin_root / "state" / "learning.lock").exists()


def test_session_end_toggle_off(plugin_root):
    """Verify that toggle-off (hooks.session_end.learning_extraction = False) makes it a no-op."""
    write_features(plugin_root, {"hooks": {"session_end": {"learning_extraction": False}}})

    payload = {
        "workspace_root": str(plugin_root),
        "transcript": [{"role": "user", "text": "turn"} for _ in range(10)]
    }

    res = run_hook(SESSION_END_HOOK, payload, plugin_root=plugin_root)
    assert res.returncode == 0
    # No lockfile should be created
    assert not (plugin_root / "state" / "learning.lock").exists()


def test_session_end_min_turns_threshold(plugin_root):
    """Verify that sessions with fewer than 10 turns are skipped."""
    write_features(plugin_root, {"hooks": {"session_end": {"learning_extraction": True}}})

    # 9 turns (fewer than 10)
    payload = {
        "workspace_root": str(plugin_root),
        "transcript": [{"role": "user", "text": "turn"} for _ in range(9)]
    }

    res = run_hook(SESSION_END_HOOK, payload, plugin_root=plugin_root)
    assert res.returncode == 0
    assert not (plugin_root / "state" / "learning.lock").exists()


def test_session_end_lockfile_exclusion(plugin_root):
    """Verify that an existing lockfile prevents overlapping extractions."""
    write_features(plugin_root, {"hooks": {"session_end": {"learning_extraction": True}}})

    # Create pre-existing lockfile
    lockfile = plugin_root / "state" / "learning.lock"
    lockfile.write_text("locked")

    payload = {
        "workspace_root": str(plugin_root),
        "transcript": [{"role": "user", "text": "turn"} for _ in range(10)]
    }

    res = run_hook(SESSION_END_HOOK, payload, plugin_root=plugin_root)
    assert res.returncode == 0
    # Lockfile should still exist but no secondary extraction was spawned
    assert lockfile.read_text() == "locked"


def test_session_end_fail_open_behavior(plugin_root):
    """Verify fail-open behavior (logs errors but exits 0 on bad/missing input)."""
    # No features.json written => load_features defaults or fails open
    res = run_hook(SESSION_END_HOOK, {}, plugin_root=plugin_root)
    assert res.returncode == 0


def test_session_end_stale_lockfile_recovery_mtime(plugin_root):
    """Verify that a lockfile older than 5 minutes is treated as stale and recovered."""
    write_features(plugin_root, {"hooks": {"session_end": {"learning_extraction": True}}})

    lockfile = plugin_root / "state" / "learning.lock"
    lockfile.write_text("session_id=old_session\npid=12345\n")

    # Set its mtime to 6 minutes ago
    import time
    os.utime(lockfile, (time.time() - 360, time.time() - 360))

    payload = {
        "workspace_root": str(plugin_root),
        "transcript": [{"role": "user", "text": "turn"} for _ in range(10)]
    }

    res = run_hook(SESSION_END_HOOK, payload, {"HARNESS_SESSION_ID": "new_session"}, plugin_root=plugin_root)
    assert res.returncode == 0

    # The lockfile should have been updated to the new session ID and contains pid
    lock_text = lockfile.read_text()
    assert "session_id=new_session" in lock_text
    assert "pid=" in lock_text
    assert "pid=12345" not in lock_text


def test_session_end_stale_lockfile_recovery_dead_pid(plugin_root):
    """Verify that a lockfile with a dead PID is recovered even if not old."""
    write_features(plugin_root, {"hooks": {"session_end": {"learning_extraction": True}}})

    lockfile = plugin_root / "state" / "learning.lock"
    lockfile.write_text("session_id=old_session\npid=999999\n")

    payload = {
        "workspace_root": str(plugin_root),
        "transcript": [{"role": "user", "text": "turn"} for _ in range(10)]
    }

    res = run_hook(SESSION_END_HOOK, payload, {"HARNESS_SESSION_ID": "new_session"}, plugin_root=plugin_root)
    assert res.returncode == 0

    lock_text = lockfile.read_text()
    assert "session_id=new_session" in lock_text
    assert "pid=" in lock_text
    assert "pid=999999" not in lock_text


def test_session_end_non_stale_live_pid(plugin_root):
    """Verify that a lockfile with a live PID is NOT recovered."""
    write_features(plugin_root, {"hooks": {"session_end": {"learning_extraction": True}}})

    lockfile = plugin_root / "state" / "learning.lock"
    lockfile.write_text(f"session_id=old_session\npid={os.getpid()}\n")

    payload = {
        "workspace_root": str(plugin_root),
        "transcript": [{"role": "user", "text": "turn"} for _ in range(10)]
    }

    res = run_hook(SESSION_END_HOOK, payload, {"HARNESS_SESSION_ID": "new_session"}, plugin_root=plugin_root)
    assert res.returncode == 0

    # The lockfile should NOT be updated, keeping the old session_id and PID
    lock_text = lockfile.read_text()
    assert "session_id=old_session" in lock_text
    assert f"pid={os.getpid()}" in lock_text
