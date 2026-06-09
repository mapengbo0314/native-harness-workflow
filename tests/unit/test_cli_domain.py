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


def test_domain_init_honours_platform_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setattr(
        "sys.argv",
        ["harness-wf", "domain-init", "--project-path", str(tmp_path), "--platform", "gemini"],
    )
    calls = {}
    with patch.object(cli, "run_domain_init", side_effect=lambda p, **k: calls.update(p=p, kw=k)):
        cli.main()
    assert calls["kw"].get("platform") == "gemini"


def test_domain_compile_honours_platform_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setattr(
        "sys.argv",
        ["harness-wf", "domain-compile", "--project-path", str(tmp_path), "--platform", "gemini"],
    )
    calls = {}
    with patch.object(cli, "run_domain_compile", side_effect=lambda p, **k: calls.update(p=p, kw=k)):
        cli.main()
    assert ".gemini" in str(calls["kw"]["manifest_path"])
    assert ".gemini" in str(calls["kw"]["reference_dir"])


def test_post_mint_domain_init_is_platform_aware(monkeypatch, tmp_path):
    """The post-mint domain scaffold helper must compute paths from the active
    platform profile (non-claude mints write under the right config dir)."""
    captured = {}

    def _fake_init(project_path, **kwargs):
        captured["project_path"] = project_path
        captured["kwargs"] = kwargs
        from pathlib import Path as _P
        return _P(project_path) / "x"

    # The helper that cli.main() calls post-mint with the active platform.
    cli._post_mint_domain_init(str(tmp_path), "gemini", run_init=_fake_init)

    assert captured["project_path"] == str(tmp_path)
    # platform threaded through so seed.py resolves the .gemini location
    assert captured["kwargs"].get("platform") == "gemini"
