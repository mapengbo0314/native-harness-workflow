"""F4 steering wiring: the per-prompt hook computes the search-first gate
predicate (toggle on + research_done unset) on Branch B only and threads it
into build_context as ``search_first_pending``; the inline fallback SYSTEM
STATE carries the same line (m1)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "src" / "harness" / "templates" / "boilerplate" / "hooks"


@pytest.fixture()
def hook_module(monkeypatch):
    monkeypatch.syspath_prepend(str(HOOKS_DIR))
    import harness.domain.model as _model
    import harness.runtime.context_builder as _cb
    monkeypatch.setitem(sys.modules, "model", _model)
    monkeypatch.setitem(sys.modules, "context_builder", _cb)
    spec = importlib.util.spec_from_file_location(
        "prompt_classifier_sfg", HOOKS_DIR / "prompt_classifier.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def hook_common():
    spec = importlib.util.spec_from_file_location(
        "hook_common_sfg_unit", HOOKS_DIR / "hook_common.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def plugin_root(tmp_path):
    (tmp_path / "state").mkdir()
    return tmp_path


def test_pending_true_on_branch_b_without_research(hook_module, plugin_root):
    assert hook_module._search_first_pending("B", plugin_root, "s1") is True


def test_pending_false_once_research_recorded(hook_module, hook_common, plugin_root):
    hook_common.set_research_done(plugin_root, "s1", note="researched")
    assert hook_module._search_first_pending("B", plugin_root, "s1") is False


def test_pending_skipped_on_non_b_branches(hook_module, plugin_root):
    for branch in ("A", "C", "D", "E"):
        assert hook_module._search_first_pending(branch, plugin_root, "s1") is False


def test_pending_false_when_toggle_off(hook_module, plugin_root):
    (plugin_root / "features.json").write_text(
        json.dumps({"pipeline": {"dispatcher": {"gates": {"search_first": False}}}})
    )
    assert hook_module._search_first_pending("B", plugin_root, "s1") is False


def test_call_site_threads_kwarg_and_fallback_has_line():
    """m1 contract: the build_context call passes search_first_pending, and the
    inline fallback SYSTEM STATE renders the same gate line."""
    source = (HOOKS_DIR / "prompt_classifier.py").read_text(encoding="utf-8")
    assert "search_first_pending=" in source, "build_context call must thread the gate flag"
    # The inline fallback (used when context_builder import fails) must carry it too.
    fallback_start = source.find("context_builder failed")
    assert fallback_start != -1
    fallback_block = source[fallback_start:fallback_start + 1200]
    assert "Search-First Gate" in fallback_block, "inline fallback must render the gate line"
