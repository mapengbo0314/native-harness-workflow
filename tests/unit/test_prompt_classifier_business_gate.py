"""The per-prompt hook must only read domain.json on branches where
build_context will actually inject the business digest (B/C) — every other
prompt skips the manifest I/O entirely (UserPromptSubmit is a hot path)."""
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
    # The deployed plugin lays model.py / context_builder.py flat next to the
    # hooks; in the repo they live in the harness package. Alias them.
    import harness.domain.model as _model
    import harness.runtime.context_builder as _cb
    monkeypatch.setitem(sys.modules, "model", _model)
    monkeypatch.setitem(sys.modules, "context_builder", _cb)
    spec = importlib.util.spec_from_file_location(
        "prompt_classifier_boilerplate", HOOKS_DIR / "prompt_classifier.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_manifest(tmp_path, business):
    p = tmp_path / "domain.json"
    p.write_text(json.dumps({"schema_version": 1, "business": business}))
    return p


def test_business_loaded_on_planning_branch(hook_module, tmp_path, monkeypatch):
    biz = {"direction": "Win SMB invoicing"}
    monkeypatch.setenv("DOMAIN_JSON_PATH", str(_write_manifest(tmp_path, biz)))
    assert hook_module._load_business("B") == biz


def test_business_skipped_on_non_business_branches(hook_module, tmp_path, monkeypatch):
    manifest = _write_manifest(tmp_path, {"direction": "X"})
    monkeypatch.setenv("DOMAIN_JSON_PATH", str(manifest))
    reads: list[str] = []
    orig_load = sys.modules["model"].OpsManifest.load

    def counting_load(path):
        reads.append(str(path))
        return orig_load(path)

    monkeypatch.setattr(sys.modules["model"].OpsManifest, "load", staticmethod(counting_load))
    for branch in ("A", "D", "E"):
        assert hook_module._load_business(branch) == {}
    assert reads == []  # no manifest I/O off the B/C branches
