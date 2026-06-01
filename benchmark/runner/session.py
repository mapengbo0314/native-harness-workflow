"""Spawn a Claude CLI session for a benchmark scenario and capture the transcript."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
TARGET_PROJECT = FIXTURES_DIR / "target_project"


@contextmanager
def _prepared_project(config: str):
    """Copy target_project to a temp dir and overlay the config, then clean up."""
    with tempfile.TemporaryDirectory(prefix="harness-bench-") as tmp:
        project = Path(tmp) / "project"
        shutil.copytree(TARGET_PROJECT, project)

        config_dir = FIXTURES_DIR / "configs" / config
        if config == "minimal":
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
        input="2\n",  # select Claude Code (option 2) non-interactively
        check=True,
        capture_output=True,
        text=True,
    )


@dataclass
class SessionResult:
    scenario_id: str
    config: str
    session_id: str
    turns: int
    transcript: list[str]
    langfuse_trace_id: str | None = None
    error: str | None = None


def run_scenario(
    scenario_path: Path,
    config: str,
    timeout: int = 300,
) -> SessionResult:
    """Run a single scenario against a given config and return the transcript.

    Args:
        scenario_path: Path to the scenario .md file
        config: One of 'no_harness', 'minimal', 'full_harness'
        timeout: Max seconds before aborting
    """
    scenario_id = scenario_path.stem
    session_id = f"benchmark-{config}-{scenario_id}-{uuid.uuid4().hex[:8]}"
    prompt = scenario_path.read_text()
    env = {**os.environ, "HARNESS_SESSION_ID": session_id}

    with _prepared_project(config) as project:
        plugin_dir = project / ".claude" / "harness-wf-plugin"
        plugin_flag = ["--plugin-dir", str(plugin_dir)] if plugin_dir.exists() else []
        cmd = ["claude", "--print", "--dangerously-skip-permissions"] + plugin_flag

        try:
            result = subprocess.run(
                cmd, cwd=project, env=env, input=prompt,
                capture_output=True, text=True, timeout=timeout,
            )
            return SessionResult(
                scenario_id=scenario_id, config=config, session_id=session_id,
                turns=_count_turns(result.stdout),
                transcript=result.stdout.splitlines(),
            )
        except subprocess.TimeoutExpired:
            return SessionResult(
                scenario_id=scenario_id, config=config, session_id=session_id,
                turns=0, transcript=[], error="timeout",
            )


def _count_turns(transcript: str) -> int:
    """Count assistant response blocks as a proxy for turns."""
    return transcript.count("\n\nHuman:") + 1
