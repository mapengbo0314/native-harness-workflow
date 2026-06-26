"""Increment 2 (plugin-selector): CLI `features list` / `enable` / `disable`.

TDD — written BEFORE the helpers/runners exist.
Pins:
  - valid_feature_key: known leaf paths accepted; unknown rejected; free-form
    rules_packs.languages.<lang> accepted
  - format_features_status: on/off markers reflect the data
  - run_features_set: read features.yaml -> apply_toggle (cascade) -> write yaml
    -> compile features.json; unknown key exits 1; missing yaml exits 1
  - run_features_list: prints a status line per known key
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FULL_YAML = """\
rules_packs:
  enabled: true
  languages:
services:
  session_memory:
    enabled: true
hooks:
  session_end:
    learning_extraction: true
pipeline:
  dispatcher:
    gates:
      search_first: true
      adversary_exit: true
skills:
  continuous-learning: true
  search-first: true
  adversary-pipeline: true
branches:
  plan_a_bugs: true
  plan_b_discovery: true
  plan_c_readonly: true
  plan_d_execution: true
  plan_e_answer: true
"""


def _write_full_yaml(root: Path) -> None:
    (root / "features.yaml").write_text(FULL_YAML, encoding="utf-8")


# ---------------------------------------------------------------------------
# valid_feature_key
# ---------------------------------------------------------------------------


def test_valid_feature_key_accepts_known_leaves():
    from harness.init.features import valid_feature_key

    assert valid_feature_key("services.session_memory.enabled") is True
    assert valid_feature_key("pipeline.dispatcher.gates.search_first") is True
    assert valid_feature_key("branches.plan_d_execution") is True
    assert valid_feature_key("skills.continuous-learning") is True


def test_valid_feature_key_accepts_freeform_language():
    from harness.init.features import valid_feature_key

    assert valid_feature_key("rules_packs.languages.python") is True


def test_valid_feature_key_rejects_unknown():
    from harness.init.features import valid_feature_key

    assert valid_feature_key("bogus.key") is False
    assert valid_feature_key("branches.plan_z_unknown") is False


# ---------------------------------------------------------------------------
# format_features_status
# ---------------------------------------------------------------------------


def test_format_features_status_marks_on_and_off():
    from harness.init.features import format_features_status

    data = {
        "services": {"session_memory": {"enabled": False}},
        "branches": {"plan_d_execution": True},
    }
    out = format_features_status(data)
    assert "[ ] services.session_memory.enabled" in out
    assert "[x] branches.plan_d_execution" in out


def test_format_features_status_absent_key_reads_as_on():
    from harness.init.features import format_features_status

    # Fail-open: a key absent from data is shown as on (matches feature_enabled).
    out = format_features_status({})
    assert "[x] pipeline.dispatcher.gates.search_first" in out


# ---------------------------------------------------------------------------
# run_features_set: toggle + cascade + compile
# ---------------------------------------------------------------------------


def test_run_features_set_disable_cascades_and_compiles(tmp_path):
    from harness.init.cli import run_features_set

    _write_full_yaml(tmp_path)
    run_features_set(str(tmp_path), "services.session_memory.enabled", False)

    compiled = json.loads((tmp_path / "features.json").read_text(encoding="utf-8"))
    assert compiled["services"]["session_memory"]["enabled"] is False
    # Cascade: features depending on session_memory are also off.
    assert compiled["pipeline"]["dispatcher"]["gates"]["search_first"] is False
    assert compiled["hooks"]["session_end"]["learning_extraction"] is False


def test_run_features_set_rejects_unknown_key(tmp_path, capsys):
    from harness.init.cli import run_features_set

    _write_full_yaml(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        run_features_set(str(tmp_path), "bogus.key", False)
    assert exc_info.value.code == 1
    assert "[HARNESS] ERROR" in capsys.readouterr().out


def test_run_features_set_missing_yaml_exits_1(tmp_path, capsys):
    from harness.init.cli import run_features_set

    with pytest.raises(SystemExit) as exc_info:
        run_features_set(str(tmp_path), "rules_packs.enabled", False)
    assert exc_info.value.code == 1
    assert "features.yaml" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# run_features_list
# ---------------------------------------------------------------------------


def test_run_features_list_prints_status(tmp_path, capsys):
    from harness.init.cli import run_features_list
    from harness.init.features import compile_features

    _write_full_yaml(tmp_path)
    compile_features(tmp_path)
    run_features_list(str(tmp_path))

    out = capsys.readouterr().out
    assert "[x] branches.plan_a_bugs" in out
    assert "services.session_memory.enabled" in out


# ---------------------------------------------------------------------------
# Increment 3: interactive toggle — pure view-model + non-TTY fallback
# ---------------------------------------------------------------------------


def test_build_checklist_rows_reflect_state():
    from harness.init.features import build_checklist

    data = {"services": {"session_memory": {"enabled": False}}}
    rows = build_checklist(data)
    # Rows are (key, is_on); ordering is stable/sorted.
    assert rows == sorted(rows, key=lambda r: r[0])
    by_key = dict(rows)
    assert by_key["services.session_memory.enabled"] is False
    # Absent keys read as on (fail-open).
    assert by_key["branches.plan_a_bugs"] is True


def test_toggle_at_flips_row_and_cascades():
    from harness.init.features import build_checklist, toggle_at

    data = {
        "services": {"session_memory": {"enabled": True}},
        "pipeline": {"dispatcher": {"gates": {"search_first": True}}},
    }
    rows = build_checklist(data)
    idx = [k for k, _ in rows].index("services.session_memory.enabled")
    new_data = toggle_at(data, idx)
    # Flipped off, and the dependent cascaded off too.
    assert new_data["services"]["session_memory"]["enabled"] is False
    assert new_data["pipeline"]["dispatcher"]["gates"]["search_first"] is False
    # Original untouched (immutability).
    assert data["services"]["session_memory"]["enabled"] is True


def test_run_features_toggle_non_tty_falls_back_to_list(tmp_path, capsys, monkeypatch):
    from harness.init.cli import run_features_toggle
    from harness.init.features import compile_features

    _write_full_yaml(tmp_path)
    compile_features(tmp_path)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False, raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)

    # Must not raise / must not enter curses; prints a message + the status list.
    run_features_toggle(str(tmp_path))
    out = capsys.readouterr().out
    assert "[x] branches.plan_a_bugs" in out
    assert "TTY" in out or "terminal" in out
