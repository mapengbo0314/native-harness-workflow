"""Spawn CLI sessions for benchmark scenarios and capture transcripts."""
from __future__ import annotations

import json
import os
import sys
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .providers import TokenUsage, run_agent_turn

_RTK_HOOK_COMMAND = "rtk hook claude"
_RTK_SYSTEM_PROMPT = (
    "RTK is active. Prefix every shell command with `rtk` to compress output "
    "(e.g. `rtk git status`, `rtk pytest`, `rtk ls`). "
    "This reduces token consumption 60-90% per command."
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
TARGET_PROJECT = FIXTURES_DIR / "target_project"


@dataclass
class Turn:
    user: str
    assistant: str


@dataclass
class SessionResult:
    scenario_id: str
    config: str
    session_id: str
    provider: str
    turns: list[Turn]
    error: str | None = None
    agent_usage: TokenUsage = field(default_factory=TokenUsage)

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def full_transcript(self) -> str:
        parts = []
        for t in self.turns:
            parts.append(f"USER: {t.user.strip()}")
            parts.append(f"ASSISTANT: {t.assistant.strip()}")
        return "\n\n".join(parts)


@contextmanager
def _prepared_project(config: str, provider: str):
    """Copy target_project to a temp dir, overlay config, then clean up."""
    with tempfile.TemporaryDirectory(prefix="harness-bench-") as tmp:
        project = Path(tmp) / "project"
        shutil.copytree(TARGET_PROJECT, project)

        # Git repo required for Claude Code hooks to fire in --print mode
        subprocess.run(["git", "init"], cwd=project, capture_output=True, check=True)
        subprocess.run(["git", "add", "."], cwd=project, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "init", "--allow-empty"],
            cwd=project, capture_output=True, check=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "bench", "GIT_AUTHOR_EMAIL": "bench@bench",
                 "GIT_COMMITTER_NAME": "bench", "GIT_COMMITTER_EMAIL": "bench@bench"},
        )

        if config == "minimal":
            config_dir = FIXTURES_DIR / "configs" / "minimal"
            for f in config_dir.glob("*"):
                shutil.copy(f, project / f.name)
        elif config == "full_harness":
            _mint_harness(project, provider)
        elif config == "rtk":
            _inject_rtk_hook(project, provider)
        elif config == "full_harness_rtk":
            _mint_harness(project, provider)
            _inject_rtk_hook(project, provider)
        # no_harness: nothing to overlay

        yield project


def _mint_harness(project: Path, provider: str) -> None:
    """Run harness-wf init to install the full plugin into the temp project."""
    platform_choice = {"claude": "2\n", "codex": "5\n"}[provider]
    repo_root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            [str(repo_root / "src"), os.environ.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep),
    }
    command = [shutil.which("harness-wf") or sys.executable]
    if command[0] == sys.executable:
        command.extend(["-m", "harness.init.cli"])
    command.extend(["init", "--project-path", str(project)])

    subprocess.run(
        command,
        input=platform_choice,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _inject_rtk_hook(project: Path, provider: str) -> None:
    """Merge RTK's PreToolUse hook into .claude/settings.json.

    Note: PreToolUse hooks don't fire in --print mode; the RTK system prompt
    injected in run_scenario() is the active instruction path for benchmarks.
    The hook config ensures correct behaviour in interactive / non-print runs.
    """
    if not shutil.which("rtk"):
        print("  WARNING: rtk not found on PATH — hook written but will fail at runtime")

    if provider != "claude":
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


def run_scenario(
    scenario_path: Path,
    config: str,
    provider: str = "claude",
    timeout: int = 300,
) -> SessionResult:
    """Run a scenario (single or multi-turn) against a config."""
    scenario_def = yaml.safe_load(scenario_path.read_text())
    scenario_id = scenario_def.get("id", scenario_path.stem)
    session_id = f"benchmark-{config}-{scenario_id}-{uuid.uuid4().hex[:8]}"
    env = {**os.environ, "HARNESS_SESSION_ID": session_id}

    # Support both old .md single-turn and new .yaml multi-turn
    if isinstance(scenario_def, dict) and "turns" in scenario_def:
        turn_prompts = [t["user"] for t in scenario_def["turns"]]
    else:
        # Legacy .md — treat whole file as a single turn
        turn_prompts = [scenario_path.read_text()]

    with _prepared_project(config, provider) as project:
        plugin_dir = project / ".claude" / "harness-wf-plugin"
        system_prompt = (
            _RTK_SYSTEM_PROMPT
            if config in ("rtk", "full_harness_rtk") else None
        )

        turns: list[Turn] = []
        agent_usage = TokenUsage()
        provider_session_id = None
        error = None
        try:
            for prompt in turn_prompts:
                turn_result = run_agent_turn(
                    provider=provider,
                    prompt=prompt,
                    project=project,
                    timeout=timeout,
                    session_id=provider_session_id,
                    plugin_dir=plugin_dir,
                    system_prompt=system_prompt,
                    env=env,
                )
                provider_session_id = turn_result.session_id
                error = turn_result.error
                agent_usage.add(turn_result.usage)
                turns.append(Turn(user=prompt, assistant=turn_result.transcript))
                if error:
                    break
        except subprocess.TimeoutExpired:
            return SessionResult(
                scenario_id=scenario_id, config=config, session_id=session_id,
                provider=provider, turns=turns, error="timeout",
                agent_usage=agent_usage,
            )

    return SessionResult(
        scenario_id=scenario_id, config=config, session_id=session_id, turns=turns,
        provider=provider, error=error, agent_usage=agent_usage,
    )
