"""Unit tests for harness.domain.detect — stack detection via GitHub Linguist
(/languages API) with an offline extension fallback, and frameworks/services via
cdxgen. All external calls (git, HTTP, npx) are injected and faked here."""
from __future__ import annotations

import json
from types import SimpleNamespace

from harness.domain import detect


def _run_ok(stdout: str):
    return lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=stdout, stderr="")


def _run_fail(cmd, **kw):
    return SimpleNamespace(returncode=1, stdout="", stderr="boom")


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

def test_detect_frameworks_parses_cdxgen_bom(tmp_path):
    bom = {
        "components": [
            {"name": "fastapi", "type": "framework"},
            {"name": "requests", "type": "library"},
            {"name": "myapp", "type": "application"},
        ],
        "services": [{"name": "postgres"}, {"name": "redis"}],
    }
    run = _run_ok(json.dumps(bom))
    out = detect.detect_frameworks(tmp_path, run=run)
    assert "fastapi" in out["frameworks"]
    assert "myapp" in out["frameworks"]
    assert "requests" not in out["frameworks"]   # plain library, not a framework
    assert out["services"] == ["postgres", "redis"]


def test_detect_frameworks_degrades_on_failure(tmp_path):
    out = detect.detect_frameworks(tmp_path, run=_run_fail)
    assert out == {"frameworks": [], "services": []}


def test_detect_frameworks_degrades_on_bad_json(tmp_path):
    out = detect.detect_frameworks(tmp_path, run=_run_ok("not json"))
    assert out == {"frameworks": [], "services": []}


# --- combined stack --------------------------------------------------------

def test_detect_stack_combines_and_dedups(tmp_path):
    run = _run_ok("git@github.com:acme/widgets.git\n")
    http_get = lambda url: {"Python": 5000}
    bom = {"components": [{"name": "fastapi", "type": "framework"}], "services": []}
    out = detect.detect_stack(
        tmp_path, run=run, http_get=http_get,
        frameworks_fn=lambda p, **k: detect.detect_frameworks(p, run=_run_ok(json.dumps(bom))),
    )
    assert out == ["Python", "fastapi"]


def test_detect_stack_empty_when_all_fail(tmp_path):
    out = detect.detect_stack(
        tmp_path, run=_run_fail, http_get=lambda u: None,
        frameworks_fn=lambda p, **k: {"frameworks": [], "services": []},
    )
    assert out == []
