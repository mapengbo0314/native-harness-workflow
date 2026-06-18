"""Shared harness setup utilities for Claude Code and Codex adapters.

Extracted from benchmark/runner/session.py so both adapters can share the
same logic for preparing a workspace with the native-harness config.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]  # benchmark/clawbench_v2/adapters/../../.. == repo root
_FIXTURES_DIR = _REPO_ROOT / "benchmark" / "fixtures"

_RTK_HOOK_COMMAND = "rtk hook claude"


def prepare_workspace_for_config(workspace: Path, harness_config: str, provider: str = "claude") -> None:
    """Overlay harness config files onto an already-populated workspace.

    Args:
        workspace:       The sandbox workspace directory (fixtures already copied in).
        harness_config:  One of no_harness, minimal, full_harness, rtk, full_harness_rtk.
        provider:        "claude" or "codex" — used by _mint_harness to pick the platform.
    """
    if harness_config == "no_harness":
        # Nothing to add — plain workspace.
        return

    # Ensure workspace has a git repo so Claude Code hooks fire correctly.
    _ensure_git_repo(workspace)

    if harness_config == "minimal":
        _copy_minimal_config(workspace)

    elif harness_config == "full_harness":
        _mint_harness(workspace, provider)

    elif harness_config == "rtk":
        _inject_rtk_hook(workspace, provider)

    elif harness_config == "full_harness_rtk":
        _mint_harness(workspace, provider, enable_rtk=True)

    elif harness_config == "ecc":
        # ECC plugin lives in the shared cache; no per-workspace copy needed.
        # _ensure_git_repo already called above; nothing else to prepare here.
        pass

    else:
        raise ValueError(f"Unknown harness_config: {harness_config!r}")


def _ensure_git_repo(project: Path) -> None:
    """Initialize a bare git repo in the project dir if one doesn't exist yet."""
    git_dir = project / ".git"
    if git_dir.exists():
        return
    subprocess.run(["git", "init"], cwd=project, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=project, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--allow-empty"],
        cwd=project,
        capture_output=True,
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "bench",
            "GIT_AUTHOR_EMAIL": "bench@bench",
            "GIT_COMMITTER_NAME": "bench",
            "GIT_COMMITTER_EMAIL": "bench@bench",
        },
    )


def _copy_minimal_config(project: Path) -> None:
    """Copy CLAUDE.md / AGENTS.md from the minimal config fixture."""
    config_dir = _FIXTURES_DIR / "configs" / "minimal"
    if not config_dir.is_dir():
        raise FileNotFoundError(f"Minimal config dir not found: {config_dir}")
    for f in config_dir.glob("*"):
        shutil.copy(f, project / f.name)


def _mint_harness(
    project: Path,
    provider: str,
    *,
    enable_rtk: bool = False,
) -> None:
    """Run `harness-wf init` to install the full plugin into the project."""
    # Map provider name to platform choice number shown by harness-wf init prompt
    platform_choice = {"claude": "2\n", "codex": "5\n"}[provider]
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            [str(_REPO_ROOT / "src"), os.environ.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep),
    }
    command = [shutil.which("harness-wf") or sys.executable]
    if command[0] == sys.executable:
        command.extend(["-m", "harness.init.cli"])
    command.extend(["init", "--project-path", str(project)])
    if enable_rtk:
        command.append("--install-rtk")

    subprocess.run(
        command,
        input=platform_choice,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    _populate_benchmark_domain_json(project, provider)


def _populate_benchmark_domain_json(project: Path, provider: str) -> None:
    """Fill in test/stack in the scaffolded domain.json so domain_ops returns useful data."""
    config_dir = {"claude": ".claude", "codex": ".codex"}.get(provider, ".claude")
    domain_json_path = project / config_dir / "harness-wf-plugin" / "domain" / "domain.json"
    if not domain_json_path.exists():
        return
    try:
        data = json.loads(domain_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    data["stack"] = ["Python", "pytest"]
    data["test"] = {"default": "pytest tests/ -v"}
    data["references"] = {
        "README.md": "Benchmark target project — minimal Python codebase with deliberate defects",
        "src/": "Source modules under test",
        "tests/": "pytest test suite",
    }
    domain_json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _inject_rtk_hook(project: Path, provider: str) -> None:
    """Merge RTK's PreToolUse hook into .claude/settings.json.

    Note: PreToolUse hooks don't fire in --print mode; the RTK system prompt
    injected by the adapter is the active instruction path for benchmarks.
    The hook config ensures correct behaviour in interactive / non-print runs.
    """
    if not shutil.which("rtk"):
        print("  WARNING: rtk not found on PATH — hook written but will fail at runtime")

    if provider != "claude":
        print(
            f"  WARNING: RTK hook skipped for {provider} — "
            "only system prompt injection applied. "
            "RTK compliance for this run depends entirely on the prompt."
        )
        return

    claude_dir = project / ".claude"
    claude_dir.mkdir(exist_ok=True)
    settings_path = claude_dir / "settings.json"

    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            pass

    pre_tool_use: list = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])

    already_present = any(
        any(_RTK_HOOK_COMMAND in h.get("command", "") for h in entry.get("hooks", []))
        for entry in pre_tool_use
    )
    if not already_present:
        pre_tool_use.append({
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": _RTK_HOOK_COMMAND}],
        })

    settings_path.write_text(json.dumps(settings, indent=2))
