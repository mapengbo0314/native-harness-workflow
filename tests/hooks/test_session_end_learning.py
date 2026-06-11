"""Phase 3 (ECC feature port): SessionEnd hook and learning extraction tests."""
from __future__ import annotations

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

SESSION_END_HOOK = HOOKS_DIR / "session_end.py"


@pytest.fixture
def plugin_root(tmp_path):
    """A fresh plugin root with a state/ subdirectory."""
    (tmp_path / "state").mkdir()
    return tmp_path


def write_features(root: Path, data: dict) -> None:
    (root / "features.json").write_text(json.dumps(data, ensure_ascii=False))


def run_hook(hook_path: Path, input_payload: dict, env_overrides: dict | None = None):
    """Run a hook subprocess and return the CompletedProcess."""
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(hook_path.parent.parent)}
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

    res = run_hook(SESSION_END_HOOK, payload, {"HARNESS_INTERNAL_LLM_CALL": "1"})
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

    res = run_hook(SESSION_END_HOOK, payload)
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

    res = run_hook(SESSION_END_HOOK, payload)
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

    res = run_hook(SESSION_END_HOOK, payload)
    assert res.returncode == 0
    # Lockfile should still exist but no secondary extraction was spawned
    assert lockfile.read_text() == "locked"


def test_session_end_fail_open_behavior(plugin_root):
    """Verify fail-open behavior (logs errors but exits 0 on bad/missing input)."""
    # No features.json written => load_features defaults or fails open
    res = run_hook(SESSION_END_HOOK, {})
    assert res.returncode == 0
