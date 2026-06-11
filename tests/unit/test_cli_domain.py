"""Wiring tests: `harness-wf domain-init` / `domain-compile` parse and route to
the domain functions without touching the npx/CodeGraph init path."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from harness.init import cli


def test_platform_flag_rejects_unknown_value(monkeypatch, tmp_path):
    """--platform must constrain to known platforms (argparse choices=) so an
    invalid value fails cleanly with exit code 2 instead of silently passing
    through to load_profile()."""
    monkeypatch.setattr(
        "sys.argv",
        ["harness-wf", "update", "--project-path", str(tmp_path), "--platform", "bogus"],
    )
    with pytest.raises(SystemExit) as exc:
        cli.parse_args()
    assert exc.value.code == 2


@pytest.mark.parametrize("platform", ["claude", "gemini", "codex", "cursor", "generic"])
def test_platform_flag_accepts_known_values(monkeypatch, tmp_path, platform):
    monkeypatch.setattr(
        "sys.argv",
        ["harness-wf", "update", "--project-path", str(tmp_path), "--platform", platform],
    )
    assert cli.parse_args().platform == platform


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


def test_domain_next_steps_points_at_platform_reference_dir():
    msg = cli._domain_next_steps("claude")
    assert ".claude/docs/reference" in msg
    assert "harness-wf domain-compile" in msg
    assert "--platform claude" in msg


def test_domain_next_steps_for_embedded_platform():
    msg = cli._domain_next_steps("gemini")
    assert ".gemini/docs/reference" in msg
    assert "--platform gemini" in msg


# ---------------------------------------------------------------------------
# GAP B: domain-refresh rewrites manifest's render_context.rules_packs filter
# ---------------------------------------------------------------------------

def _setup_refresh_project(tmp_path):
    """Scaffold a minimal project with a deployed plugin manifest (python-only)."""
    import json as _json
    import harness
    from harness.update.manifest import write_manifest as _wm

    project = tmp_path / "project"
    project.mkdir()
    plugin_dir = project / ".claude" / "harness-wf-plugin"
    plugin_dir.mkdir(parents=True)

    # Need a real pyproject.toml so write_manifest can read a version
    package_root = (
        __import__("pathlib").Path(harness.__file__).parent
    )

    # Minimal plugin structure so write_manifest can walk it
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        _json.dumps({"name": "orchestrator-plugin", "version": "1.0.0"}) + "\n"
    )

    # Write manifest with python-only rules_packs selection plus a sentinel key
    # to verify other render_context fields are preserved.
    _wm(plugin_dir, package_root, render_context={
        "platform": "claude",
        "harness_dir_name": ".claude",
        "selected_agents": [],
        "project_name": "my-proj",
        "rules_packs": {"selected": ["python"], "enabled": True},
        "sentinel_key": "must-survive",
    })

    # domain.json now reports Python + Go
    domain_dir = plugin_dir / "domain"
    domain_dir.mkdir(parents=True)
    (domain_dir / "domain.json").write_text(
        _json.dumps({"stack": ["Python", "Go"]}) + "\n"
    )

    return project, plugin_dir, package_root


def test_domain_refresh_rewrites_manifest_rules_packs_selection(tmp_path, monkeypatch):
    """After run_domain_refresh_with_sync with a new stack, the manifest's
    render_context.rules_packs.selected reflects the new stack."""
    import json as _json
    from harness.update.manifest import read_manifest
    from pathlib import Path as _P

    project, plugin_dir, _pkg_root = _setup_refresh_project(tmp_path)

    # Patch out the heavy external calls so only the manifest-rewrite path runs
    with (
        patch.object(cli, "run_domain_refresh", return_value=None),
        patch.object(cli, "compile_features", return_value=None),
        patch.object(cli, "sync_rules_packs", return_value=None),
    ):
        cli.run_domain_refresh_with_sync(str(project))

    manifest = read_manifest(plugin_dir)
    rc = manifest.get("render_context", {})
    rp = rc.get("rules_packs", {})

    assert rp.get("selected") == ["golang", "python"], (
        f"Expected ['golang', 'python'] but got {rp.get('selected')!r}"
    )
    assert rp.get("enabled") is True

    # Other render_context keys must survive
    assert rc.get("sentinel_key") == "must-survive"
    assert rc.get("platform") == "claude"
