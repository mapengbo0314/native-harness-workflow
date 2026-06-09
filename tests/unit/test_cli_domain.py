"""Wiring tests: `harness-wf domain-init` / `domain-compile` parse and route to
the domain functions without touching the npx/CodeGraph init path."""
from __future__ import annotations

from unittest.mock import patch

from harness.init import cli


def test_parse_args_accepts_domain_init(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["harness-wf", "domain-init", "--project-path", str(tmp_path)])
    assert cli.parse_args().command == "domain-init"


def test_parse_args_accepts_domain_compile(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["harness-wf", "domain-compile", "--project-path", str(tmp_path)])
    assert cli.parse_args().command == "domain-compile"


def test_main_routes_domain_init(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setattr("sys.argv", ["harness-wf", "domain-init", "--project-path", str(tmp_path)])
    calls = {}
    with patch.object(cli, "run_domain_init", side_effect=lambda p, **k: calls.update(p=p)):
        cli.main()
    assert calls["p"] == str(tmp_path)


def test_parse_args_accepts_domain_refresh(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.argv", ["harness-wf", "domain-refresh", "--project-path", str(tmp_path)])
    assert cli.parse_args().command == "domain-refresh"


def test_main_routes_domain_refresh(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setattr("sys.argv", ["harness-wf", "domain-refresh", "--project-path", str(tmp_path)])
    calls = {}
    with patch.object(cli, "run_domain_refresh", side_effect=lambda p, **k: calls.update(p=p)):
        cli.main()
    assert calls["p"] == str(tmp_path)


def test_main_routes_domain_compile(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setattr("sys.argv", ["harness-wf", "domain-compile", "--project-path", str(tmp_path)])
    calls = {}
    with patch.object(cli, "run_domain_compile", side_effect=lambda p, **k: calls.update(p=p, kw=k)):
        cli.main()
    assert calls["p"] == tmp_path  # Path(args.project_path)
    assert calls["kw"]["manifest_path"].name == "domain.json"
