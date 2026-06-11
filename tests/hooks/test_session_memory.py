"""Phase 2 (ECC feature port): session memory store tests.

Tests cover:
  - record_session_entry write/read round-trip
  - per-session isolation (two session IDs, no clobber)
  - schema_version skip on bad session files
  - corrupt file tolerance in build_session_digest
  - retention (entries older than 30 days dropped)
  - dedup and order determinism (two identical calls => byte-identical digest)
  - caps: entry count (<=6), summary truncation (<=220 chars), 8KB total
  - kind validation (invalid kind => no entry written, no crash)
  - opt-out env HARNESS_SESSION_CONTEXT=off => session_memory_save.py exits 0 (no-op)
  - feature toggle off => no-op
  - phase round-trip, phase entries, and clear (R2)
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

HOOKS_DIR = (
    Path(__file__).parent.parent.parent
    / "src/harness/templates/boilerplate/hooks"
)

SAVE_HOOK = HOOKS_DIR / "session_memory_save.py"
START_HOOK = HOOKS_DIR / "session_start.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hook_common():
    spec = importlib.util.spec_from_file_location(
        "hook_common_session_test", HOOKS_DIR / "hook_common.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def plugin_root(tmp_path):
    """A fresh plugin root with a state/ subdirectory."""
    (tmp_path / "state").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_features(root: Path, data: dict) -> None:
    (root / "features.json").write_text(json.dumps(data))


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


# ---------------------------------------------------------------------------
# record_session_entry: write/read round-trip
# ---------------------------------------------------------------------------


def test_record_entry_round_trip(hook_common, plugin_root):
    hook_common.record_session_entry(
        plugin_root, "sess1", "decision", "Use postgres", refs=["ADR-001"]
    )
    data = json.loads(
        (plugin_root / "state" / "session_memory_sess1.json").read_text()
    )
    assert data["schema_version"] == 1
    assert data["session_id"] == "sess1"
    assert len(data["entries"]) == 1
    entry = data["entries"][0]
    assert entry["kind"] == "decision"
    assert entry["summary"] == "Use postgres"
    assert entry["refs"] == ["ADR-001"]
    assert entry["schema_version"] == 1
    assert "ts" in entry


def test_record_multiple_entries_append(hook_common, plugin_root):
    hook_common.record_session_entry(plugin_root, "sessA", "decision", "First")
    hook_common.record_session_entry(plugin_root, "sessA", "blocker", "Second")
    hook_common.record_session_entry(plugin_root, "sessA", "pattern", "Third")
    data = json.loads(
        (plugin_root / "state" / "session_memory_sessA.json").read_text()
    )
    assert len(data["entries"]) == 3
    kinds = [e["kind"] for e in data["entries"]]
    assert kinds == ["decision", "blocker", "pattern"]


# ---------------------------------------------------------------------------
# Per-session isolation
# ---------------------------------------------------------------------------


def test_two_sessions_do_not_clobber(hook_common, plugin_root):
    hook_common.record_session_entry(plugin_root, "sessX", "decision", "Session X entry")
    hook_common.record_session_entry(plugin_root, "sessY", "blocker", "Session Y entry")

    data_x = json.loads(
        (plugin_root / "state" / "session_memory_sessX.json").read_text()
    )
    data_y = json.loads(
        (plugin_root / "state" / "session_memory_sessY.json").read_text()
    )
    assert len(data_x["entries"]) == 1
    assert data_x["entries"][0]["summary"] == "Session X entry"
    assert len(data_y["entries"]) == 1
    assert data_y["entries"][0]["summary"] == "Session Y entry"


# ---------------------------------------------------------------------------
# Schema-version skip in build_session_digest
# ---------------------------------------------------------------------------


def test_schema_version_skip(hook_common, plugin_root):
    # Write a file with wrong schema_version
    bad = {
        "schema_version": 99,
        "session_id": "bad",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "entries": [
            {
                "schema_version": 99,
                "ts": datetime.now(timezone.utc).isoformat(),
                "session_id": "bad",
                "kind": "decision",
                "summary": "should be skipped",
                "refs": [],
            }
        ],
        "phase": None,
    }
    (plugin_root / "state" / "session_memory_bad.json").write_text(
        json.dumps(bad)
    )
    digest = hook_common.build_session_digest(plugin_root)
    assert "should be skipped" not in digest


# ---------------------------------------------------------------------------
# Corrupt file tolerance
# ---------------------------------------------------------------------------


def test_corrupt_file_tolerance(hook_common, plugin_root):
    (plugin_root / "state" / "session_memory_corrupt.json").write_text(
        "{not valid json!!"
    )
    hook_common.record_session_entry(plugin_root, "good", "decision", "Valid entry")
    # Should not raise
    digest = hook_common.build_session_digest(plugin_root)
    assert "Valid entry" in digest


# ---------------------------------------------------------------------------
# Retention: entries older than 30 days dropped
# ---------------------------------------------------------------------------


def test_retention_drops_old_entries(hook_common, plugin_root):
    old_ts = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    recent_ts = datetime.now(timezone.utc).isoformat()

    old_file = {
        "schema_version": 1,
        "session_id": "old",
        "updated_at": old_ts,
        "entries": [
            {
                "schema_version": 1,
                "ts": old_ts,
                "session_id": "old",
                "kind": "decision",
                "summary": "ancient decision",
                "refs": [],
            }
        ],
        "phase": None,
    }
    (plugin_root / "state" / "session_memory_old.json").write_text(
        json.dumps(old_file)
    )

    recent_file = {
        "schema_version": 1,
        "session_id": "recent",
        "updated_at": recent_ts,
        "entries": [
            {
                "schema_version": 1,
                "ts": recent_ts,
                "session_id": "recent",
                "kind": "decision",
                "summary": "recent decision",
                "refs": [],
            }
        ],
        "phase": None,
    }
    (plugin_root / "state" / "session_memory_recent.json").write_text(
        json.dumps(recent_file)
    )

    digest = hook_common.build_session_digest(plugin_root)
    assert "ancient decision" not in digest
    assert "recent decision" in digest


# ---------------------------------------------------------------------------
# Dedup and order determinism
# ---------------------------------------------------------------------------


def test_dedup_same_kind_summary(hook_common, plugin_root):
    hook_common.record_session_entry(plugin_root, "d1", "decision", "Use redis")
    hook_common.record_session_entry(plugin_root, "d2", "decision", "Use redis")
    digest = hook_common.build_session_digest(plugin_root)
    # Should only appear once
    assert digest.count("Use redis") == 1


def test_digest_is_deterministic(hook_common, plugin_root):
    hook_common.record_session_entry(plugin_root, "det1", "decision", "Alpha")
    hook_common.record_session_entry(plugin_root, "det2", "blocker", "Beta")
    digest1 = hook_common.build_session_digest(plugin_root)
    digest2 = hook_common.build_session_digest(plugin_root)
    assert digest1 == digest2


def test_dedup_normalizes_case_and_whitespace(hook_common, plugin_root):
    hook_common.record_session_entry(plugin_root, "n1", "pattern", "  Use   Redis  ")
    hook_common.record_session_entry(plugin_root, "n2", "pattern", "use redis")
    digest = hook_common.build_session_digest(plugin_root)
    # dedup collapses these — only one line
    lines = [l for l in digest.splitlines() if "redis" in l.lower()]
    assert len(lines) == 1


# ---------------------------------------------------------------------------
# Caps
# ---------------------------------------------------------------------------


def test_entry_count_cap(hook_common, plugin_root):
    for i in range(10):
        hook_common.record_session_entry(
            plugin_root, f"cap{i}", "decision", f"Entry number {i}"
        )
    digest = hook_common.build_session_digest(plugin_root)
    lines = [l for l in digest.splitlines() if l.startswith("- [")]
    assert len(lines) <= 6


def test_summary_truncation(hook_common, plugin_root):
    long_summary = "X" * 300
    hook_common.record_session_entry(plugin_root, "trunc1", "decision", long_summary)
    data = json.loads(
        (plugin_root / "state" / "session_memory_trunc1.json").read_text()
    )
    stored = data["entries"][0]["summary"]
    assert len(stored) <= 220


def test_digest_8kb_cap(hook_common, plugin_root):
    # Write 6 entries, each with a 2KB ref, totaling ~12KB.
    # The 8KB byte cap should truncate the output at a newline,
    # leaving only some of the entries.
    for i in range(6):
        hook_common.record_session_entry(
            plugin_root,
            f"big{i}",
            "decision",
            f"Decision {i}",
            refs=["A" * 2000]
        )
    digest = hook_common.build_session_digest(plugin_root)
    digest_bytes = digest.encode("utf-8")

    # Must be capped at 8KB
    assert len(digest_bytes) <= 8 * 1024

    # Should contain the newest entries but not the oldest one
    assert "Decision 5" in digest
    assert "Decision 0" not in digest

    # We should have more than just the header to prove it didn't just fail
    assert len(digest_bytes) > 2000


# ---------------------------------------------------------------------------
# Kind validation
# ---------------------------------------------------------------------------


def test_invalid_kind_is_silently_rejected(hook_common, plugin_root):
    hook_common.record_session_entry(
        plugin_root, "badkind", "INVALID_KIND", "Should not appear"
    )
    path = plugin_root / "state" / "session_memory_badkind.json"
    # File may or may not exist; if it exists, entry must not be in it
    if path.exists():
        data = json.loads(path.read_text())
        assert not any(
            e.get("summary") == "Should not appear" for e in data.get("entries", [])
        )


# ---------------------------------------------------------------------------
# Phase round-trip and clear (R2)
# ---------------------------------------------------------------------------


def test_set_and_get_phase(hook_common, plugin_root):
    hook_common.set_phase(plugin_root, "phsess", "design")
    phase = hook_common.get_phase(plugin_root, "phsess")
    assert phase is not None
    assert phase["phase"] == "design"
    assert "phase_entered_at" in phase
    assert "phase_exit_artifact" in phase


def test_set_phase_with_exit_artifact(hook_common, plugin_root):
    hook_common.set_phase(plugin_root, "phsess2", "build", exit_artifact="docs/adr/001.md")
    phase = hook_common.get_phase(plugin_root, "phsess2")
    assert phase["phase"] == "build"
    assert phase["phase_exit_artifact"] == "docs/adr/001.md"


def test_get_phase_none_before_set(hook_common, plugin_root):
    phase = hook_common.get_phase(plugin_root, "nophase_sess")
    assert phase is None


def test_clear_phase(hook_common, plugin_root):
    hook_common.set_phase(plugin_root, "clrphase", "design")
    assert hook_common.get_phase(plugin_root, "clrphase") is not None
    hook_common.clear_phase(plugin_root, "clrphase")
    assert hook_common.get_phase(plugin_root, "clrphase") is None


def test_phase_is_also_recorded_as_versioned_entry(hook_common, plugin_root):
    hook_common.set_phase(plugin_root, "phentries", "review")
    hook_common.record_session_entry(plugin_root, "phentries", "decision", "Some decision")
    data = json.loads(
        (plugin_root / "state" / "session_memory_phentries.json").read_text()
    )
    assert data.get("phase") is not None
    assert data["phase"]["phase"] == "review"
    kinds = [entry["kind"] for entry in data["entries"]]
    assert kinds == ["phase", "decision"]
    phase_entry = data["entries"][0]
    assert phase_entry["schema_version"] == 1
    assert phase_entry["summary"] == "Entered phase: review"


def test_clear_phase_records_exit_artifact(hook_common, plugin_root):
    hook_common.set_phase(plugin_root, "phaseexit", "planning")
    hook_common.clear_phase(plugin_root, "phaseexit", exit_artifact="docs/design.md")
    data = json.loads(
        (plugin_root / "state" / "session_memory_phaseexit.json").read_text()
    )
    assert data["phase"] is None
    assert data["entries"][-1]["kind"] == "phase"
    assert data["entries"][-1]["summary"] == "Exited phase: planning"
    assert data["entries"][-1]["refs"] == ["docs/design.md"]


def test_phase_overwrite(hook_common, plugin_root):
    """Latest set_phase wins."""
    hook_common.set_phase(plugin_root, "overwrite", "design")
    hook_common.set_phase(plugin_root, "overwrite", "build")
    phase = hook_common.get_phase(plugin_root, "overwrite")
    assert phase["phase"] == "build"


def test_session_id_is_sanitized_for_filename(hook_common, plugin_root):
    hook_common.record_session_entry(plugin_root, "../bad/session", "decision", "Safe")
    files = sorted((plugin_root / "state").glob("session_memory_*.json"))
    assert len(files) == 1
    assert files[0].name == "session_memory_bad_session.json"


# ---------------------------------------------------------------------------
# session_memory_save.py hook: opt-out env => no-op exit 0
# ---------------------------------------------------------------------------


def test_save_hook_noop_when_env_opt_out(tmp_path):
    result = run_hook(
        SAVE_HOOK,
        {"session_id": "testsess"},
        env_overrides={"HARNESS_SESSION_CONTEXT": "off"},
    )
    assert result.returncode == 0
    # No session file should be created
    assert not list(tmp_path.glob("state/session_memory_*.json"))


def test_save_hook_noop_when_toggle_off(tmp_path):
    plugin_root = tmp_path
    (plugin_root / "state").mkdir()
    (plugin_root / "features.json").write_text(
        json.dumps({"services": {"session_memory": {"enabled": False}}})
    )
    result = subprocess.run(
        [sys.executable, str(SAVE_HOOK)],
        input=json.dumps({"session_id": "toggled_off"}),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(plugin_root),
            "HARNESS_SESSION_CONTEXT": "",
        },
    )
    assert result.returncode == 0
    assert not (plugin_root / "state" / "session_memory_toggled_off.json").exists()


def test_save_hook_creates_session_file(tmp_path):
    """When enabled (default), save hook creates/touches the session file."""
    plugin_root = tmp_path
    (plugin_root / "state").mkdir()
    result = subprocess.run(
        [sys.executable, str(SAVE_HOOK)],
        input=json.dumps({"session_id": "enabled_sess"}),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(plugin_root),
            "HARNESS_SESSION_CONTEXT": "",
        },
    )
    assert result.returncode == 0
    assert (plugin_root / "state" / "session_memory_enabled_sess.json").exists()


# ---------------------------------------------------------------------------
# session_memory_save.py: bad stdin doesn't crash (fail-open)
# ---------------------------------------------------------------------------


def test_save_hook_bad_stdin_exits_zero(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SAVE_HOOK)],
        input="not json at all!!",
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(tmp_path),
            "HARNESS_SESSION_ID": "fallback_sess",
            "HARNESS_SESSION_CONTEXT": "",
        },
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# session_start.py: opt-out env => silent exit 0
# ---------------------------------------------------------------------------


def test_start_hook_noop_when_env_opt_out(tmp_path):
    result = run_hook(
        START_HOOK,
        {},
        env_overrides={"HARNESS_SESSION_CONTEXT": "off"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_start_hook_emits_digest_when_entries_exist(tmp_path):
    plugin_root = tmp_path
    (plugin_root / "state").mkdir()

    spec = importlib.util.spec_from_file_location(
        "hc_start_test", HOOKS_DIR / "hook_common.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod.record_session_entry(plugin_root, "s1", "decision", "Use postgres")

    result = subprocess.run(
        [sys.executable, str(START_HOOK)],
        input=json.dumps({}),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(plugin_root),
            "HARNESS_SESSION_CONTEXT": "",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "hookSpecificOutput" in output
    hso = output["hookSpecificOutput"]
    assert hso["hookEventName"] == "SessionStart"
    assert "Session Memory" in hso["additionalContext"]
    assert "Use postgres" in hso["additionalContext"]


def test_start_hook_emits_nothing_when_no_entries(tmp_path):
    plugin_root = tmp_path
    (plugin_root / "state").mkdir()
    result = subprocess.run(
        [sys.executable, str(START_HOOK)],
        input=json.dumps({}),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(plugin_root),
            "HARNESS_SESSION_CONTEXT": "",
        },
    )
    assert result.returncode == 0
    # Nothing to inject → no output
    assert result.stdout.strip() == ""
