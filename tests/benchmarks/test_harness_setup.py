import subprocess

from benchmark.clawbench_v2.adapters import _harness_setup


def test_full_harness_rtk_uses_harness_rtk_flag(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setattr(_harness_setup, "_ensure_git_repo", lambda project: None)
    monkeypatch.setattr(
        _harness_setup,
        "_inject_rtk_hook",
        lambda *args, **kwargs: calls.append(("overlay", args, kwargs)),
    )
    monkeypatch.setattr(
        _harness_setup,
        "_mint_harness",
        lambda *args, **kwargs: calls.append(("mint", args, kwargs)),
    )

    _harness_setup.prepare_workspace_for_config(
        tmp_path,
        "full_harness_rtk",
        provider="claude",
    )

    assert calls == [
        ("mint", (tmp_path, "claude"), {"enable_rtk": True}),
    ]


def test_mint_harness_appends_rtk_install_cli_flag(monkeypatch, tmp_path):
    captured = {}

    monkeypatch.setattr(_harness_setup.shutil, "which", lambda name: None)

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(_harness_setup.subprocess, "run", fake_run)

    _harness_setup._mint_harness(
        tmp_path,
        "codex",
        enable_rtk=True,
    )

    assert captured["command"][-1] == "--install-rtk"
    assert captured["command"][-4:-1] == [
        "init",
        "--project-path",
        str(tmp_path),
    ]
    assert captured["kwargs"]["input"] == "5\n"
