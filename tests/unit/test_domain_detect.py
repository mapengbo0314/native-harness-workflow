"""Unit tests for harness.domain.detect — stack detection via GitHub Linguist
(/languages API) with an offline extension fallback, and frameworks/services via
cdxgen. All external calls (git, HTTP, npx) are injected and faked here."""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

from harness.domain import detect


def _run_ok(stdout: str):
    return lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def _run_fail(cmd, **kw):
    return SimpleNamespace(returncode=1, stdout="", stderr="boom")


def _run_writes_bom(bom, recorder=None):
    """Fake cdxgen runner: writes the BOM to the `-o <path>` arg (as real cdxgen
    does), recording the cmd/kwargs so tests can assert how it was invoked."""
    def run(cmd, **kw):
        if recorder is not None:
            recorder["cmd"], recorder["kw"] = cmd, kw
        out = cmd[cmd.index("-o") + 1]
        Path(out).write_text(json.dumps(bom))
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return run


# --- git remote slug -------------------------------------------------------

def test_github_slug_from_ssh(tmp_path):
    run = _run_ok("git@github.com:acme/widgets.git\n")
    assert detect._github_repo_slug(tmp_path, run=run) == "acme/widgets"


def test_github_slug_from_https(tmp_path):
    run = _run_ok("https://github.com/acme/widgets.git\n")
    assert detect._github_repo_slug(tmp_path, run=run) == "acme/widgets"


def test_github_slug_non_github_is_none(tmp_path):
    run = _run_ok("https://gitlab.com/acme/widgets.git\n")
    assert detect._github_repo_slug(tmp_path, run=run) is None


def test_github_slug_no_remote_is_none(tmp_path):
    assert detect._github_repo_slug(tmp_path, run=_run_fail) is None


# --- languages -------------------------------------------------------------

def test_detect_languages_uses_github_api_weighted(tmp_path):
    run = _run_ok("git@github.com:acme/widgets.git\n")
    http_get = lambda url: {"Python": 9000, "TypeScript": 3000, "Shell": 100}
    langs = detect.detect_languages(tmp_path, run=run, http_get=http_get)
    assert langs == ["Python", "TypeScript", "Shell"]  # sorted by bytes desc


def test_detect_languages_falls_back_to_extensions_offline(tmp_path):
    (tmp_path / "a.py").write_text("x=1\n")
    (tmp_path / "b.py").write_text("y=2\n")
    (tmp_path / "c.ts").write_text("const z=3\n")
    # GitHub slug resolves but the HTTP call fails → extension fallback.
    run = _run_ok("git@github.com:acme/widgets.git\n")
    http_get = lambda url: None
    langs = detect.detect_languages(tmp_path, run=run, http_get=http_get)
    assert langs[0] == "Python"          # 2 files beats 1
    assert "TypeScript" in langs


def test_extension_languages_no_remote(tmp_path):
    (tmp_path / "main.go").write_text("package main\n")
    langs = detect.detect_languages(tmp_path, run=_run_fail, http_get=lambda u: None)
    assert langs == ["Go"]


# --- frameworks / services via cdxgen --------------------------------------

def test_cdxgen_types_maps_and_dedups_languages():
    # TypeScript + JavaScript collapse to one cdxgen type; unknown langs dropped.
    assert detect._cdxgen_types(["Python", "TypeScript", "JavaScript", "Go", "HTML"]) == [
        "python", "javascript", "go",
    ]
    assert detect._cdxgen_types([]) == []


def test_detect_frameworks_reads_output_file(tmp_path):
    bom = {
        "components": [
            {"name": "fastapi", "type": "framework"},
            {"name": "requests", "type": "library"},
            {"name": "myapp", "type": "application"},
        ],
        "services": [{"name": "postgres"}, {"name": "redis"}],
    }
    # cdxgen writes a file (not stdout) — the BOM is read from disk.
    out = detect.detect_frameworks(tmp_path, run=_run_writes_bom(bom), languages=["Python"])
    assert "fastapi" in out["frameworks"]
    assert "myapp" in out["frameworks"]
    assert "requests" not in out["frameworks"]   # plain library, not a framework
    assert out["services"] == ["postgres", "redis"]


def test_detect_frameworks_isolates_output_and_passes_type_flags(tmp_path):
    rec = {}
    detect.detect_frameworks(
        tmp_path,
        run=_run_writes_bom({"components": [], "services": []}, recorder=rec),
        languages=["Python", "TypeScript"],
    )
    cmd, kw = rec["cmd"], rec["kw"]
    # type flags derived from languages (TS+JS dedup → one 'javascript')
    assert "python" in cmd and "javascript" in cmd
    # BOM is written under the injected temp cwd, never into the scanned repo
    out_path = cmd[cmd.index("-o") + 1]
    assert kw.get("cwd") and out_path.startswith(kw["cwd"])
    assert not out_path.startswith(str(tmp_path))
    # license fetch disabled for speed/determinism
    assert kw.get("env", {}).get("FETCH_LICENSE") == "false"


def test_detect_frameworks_scans_absolute_path(tmp_path, monkeypatch):
    # cdxgen runs with cwd set to a temp dir, so a relative project path would
    # resolve against that temp dir and scan the wrong directory. The scanned
    # path handed to cdxgen must be absolute.
    monkeypatch.chdir(tmp_path)
    rec = {}
    detect.detect_frameworks(
        ".", run=_run_writes_bom({"components": [], "services": []}, recorder=rec),
    )
    scanned = rec["cmd"][-1]
    assert os.path.isabs(scanned)
    assert Path(scanned).resolve() == tmp_path.resolve()


def test_detect_frameworks_degrades_on_failure(tmp_path):
    out = detect.detect_frameworks(tmp_path, run=_run_fail)
    assert out == {"frameworks": [], "services": []}


def test_detect_frameworks_degrades_when_no_bom_written(tmp_path):
    # cdxgen exits 0 but produces no parseable BOM file → graceful empty.
    run = lambda cmd, **kw: SimpleNamespace(returncode=0, stdout="", stderr="")
    out = detect.detect_frameworks(tmp_path, run=run)
    assert out == {"frameworks": [], "services": []}


# --- combined stack --------------------------------------------------------

def test_detect_stack_combines_and_dedups(tmp_path):
    run = _run_ok("git@github.com:acme/widgets.git\n")
    http_get = lambda url: {"Python": 5000}
    out = detect.detect_stack(
        tmp_path, run=run, http_get=http_get,
        frameworks_fn=lambda p, **k: {"frameworks": ["fastapi"], "services": []},
    )
    assert out == ["Python", "fastapi"]


def test_detect_stack_passes_detected_languages_to_frameworks(tmp_path):
    run = _run_ok("git@github.com:acme/widgets.git\n")
    http_get = lambda url: {"Python": 5000, "Go": 100}
    seen = {}

    def fw(p, **k):
        seen["languages"] = k.get("languages")
        return {"frameworks": [], "services": []}

    detect.detect_stack(tmp_path, run=run, http_get=http_get, frameworks_fn=fw)
    assert seen["languages"] == ["Python", "Go"]


def test_detect_stack_empty_when_all_fail(tmp_path):
    out = detect.detect_stack(
        tmp_path, run=_run_fail, http_get=lambda u: None,
        frameworks_fn=lambda p, **k: {"frameworks": [], "services": []},
    )
    assert out == []
