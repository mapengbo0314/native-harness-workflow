"""Spawn Claude CLI sessions for benchmark scenarios and capture transcripts."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import yaml

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
    turns: list[Turn]
    error: str | None = None

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
def _prepared_project(config: str):
    """Copy target_project to a temp dir, overlay config, then clean up."""
    with tempfile.TemporaryDirectory(prefix="harness-bench-") as tmp:
        project = Path(tmp) / "project"
        shutil.copytree(TARGET_PROJECT, project)

        if config == "minimal":
            config_dir = FIXTURES_DIR / "configs" / "minimal"
            for f in config_dir.glob("*"):
                shutil.copy(f, project / f.name)
        elif config == "full_harness":
            _mint_harness(project)
        # no_harness: nothing to overlay

        yield project


def _mint_harness(project: Path) -> None:
    """Run harness-wf init to install the full plugin into the temp project."""
    subprocess.run(
        ["harness-wf", "init", "--project-path", str(project)],
        input="2\n",  # select Claude Code non-interactively
        check=True,
        capture_output=True,
        text=True,
    )


def run_scenario(scenario_path: Path, config: str, timeout: int = 300) -> SessionResult:
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

    with _prepared_project(config) as project:
        plugin_dir = project / ".claude" / "harness-wf-plugin"
        plugin_flag = ["--plugin-dir", str(plugin_dir)] if plugin_dir.exists() else []
        base_cmd = ["claude", "--print", "--dangerously-skip-permissions"] + plugin_flag

        turns: list[Turn] = []
        try:
            for i, prompt in enumerate(turn_prompts):
                cmd = base_cmd + (["--continue"] if i > 0 else [])
                result = subprocess.run(
                    cmd, cwd=project, env=env,
                    input=prompt, capture_output=True, text=True, timeout=timeout,
                )
                turns.append(Turn(user=prompt, assistant=result.stdout))
        except subprocess.TimeoutExpired:
            return SessionResult(
                scenario_id=scenario_id, config=config, session_id=session_id,
                turns=turns, error="timeout",
            )

    return SessionResult(
        scenario_id=scenario_id, config=config, session_id=session_id, turns=turns,
    )
