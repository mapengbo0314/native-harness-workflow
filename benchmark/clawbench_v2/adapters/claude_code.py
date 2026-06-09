"""Claude Code adapter for harness-bench.

Runs the `claude --print --output-format json` CLI against a task workspace,
supporting multiple harness configuration variants (no_harness, minimal,
full_harness, rtk, full_harness_rtk).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from clawbench_v2.adapters._harness_setup import prepare_workspace_for_config
from clawbench_v2.adapters.base import BaseAdapter
from clawbench_v2.models import AdapterRunContext, AdapterRunResult

_RTK_SYSTEM_PROMPT = (
    "RTK is active. Prefix every shell command with `rtk` to compress output "
    "(e.g. `rtk git status`, `rtk pytest`, `rtk ls`). "
    "This reduces token consumption 60-90% per command."
)


def parse_claude_json_output(raw: str) -> tuple[str, dict, float]:
    """Parse --output-format json output into (transcript, usage_dict, cost_usd).

    Falls back gracefully if the output is plain text (older CLI versions).
    """
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            transcript = data.get("result", stripped)
            usage = data.get("usage", {})
            cost = float(data.get("total_cost_usd", 0.0))
            return transcript, usage, cost
        except json.JSONDecodeError:
            pass
    return stripped, {}, 0.0


class ClaudeCodeAdapter(BaseAdapter):
    name = "claude_code"

    def run(self, ctx: AdapterRunContext) -> AdapterRunResult:
        harness_config: str = str(ctx.model_config.get("harness_config", "no_harness"))

        try:
            prepare_workspace_for_config(ctx.workspace, harness_config, provider="claude")
        except Exception as exc:
            return AdapterRunResult(
                ok=False,
                command=[],
                stdout="",
                stderr=f"harness setup failed: {exc}",
                metadata={"harness_config": harness_config, "setup_error": str(exc)},
            )

        command: list[str] = [
            "claude", "--print", "--output-format", "json",
            "--dangerously-skip-permissions",
        ]

        if harness_config in ("full_harness", "full_harness_rtk"):
            plugin_dir = ctx.workspace / ".claude" / "harness-wf-plugin"
            if plugin_dir.exists():
                command.extend(["--plugin-dir", str(plugin_dir)])

        if harness_config in ("rtk", "full_harness_rtk"):
            command.extend(["--append-system-prompt", _RTK_SYSTEM_PROMPT])

        env = os.environ.copy()
        env.update(ctx.env)

        try:
            prompt_text = Path(ctx.prompt_file).read_text(encoding="utf-8")
        except OSError as exc:
            return AdapterRunResult(
                ok=False,
                command=command,
                stdout="",
                stderr=f"failed to read prompt file {ctx.prompt_file}: {exc}",
                metadata={"harness_config": harness_config},
            )

        try:
            completed = subprocess.run(
                command,
                input=prompt_text,
                cwd=str(ctx.workspace),
                env=env,
                capture_output=True,
                text=True,
                timeout=ctx.timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return AdapterRunResult(
                ok=False,
                command=command,
                stdout="",
                stderr=f"claude timed out after {ctx.timeout_sec}s",
                metadata={"harness_config": harness_config, "timeout": True},
            )

        transcript, usage, cost_usd = parse_claude_json_output(completed.stdout)
        _save_transcript(ctx.workspace, transcript)
        return AdapterRunResult(
            ok=completed.returncode == 0,
            command=command,
            stdout=transcript,
            stderr=completed.stderr,
            metadata={
                "returncode": completed.returncode,
                "harness_config": harness_config,
                "usage": usage,
                "total_cost_usd": cost_usd,
            },
        )


def _save_transcript(workspace: Path, transcript: str) -> None:
    try:
        (workspace / ".bench_transcript.txt").write_text(transcript, encoding="utf-8")
    except OSError:
        pass
