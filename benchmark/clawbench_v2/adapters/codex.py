"""Codex adapter for harness-bench.

Runs `codex exec --json` against a task workspace, supporting multiple
harness configuration variants (no_harness, minimal, full_harness, rtk,
full_harness_rtk).
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


class CodexAdapter(BaseAdapter):
    name = "codex"

    def run(self, ctx: AdapterRunContext) -> AdapterRunResult:
        harness_config: str = str(ctx.model_config.get("harness_config", "no_harness"))

        # Prepare workspace: overlay harness config files / run init
        try:
            prepare_workspace_for_config(ctx.workspace, harness_config, provider="codex")
        except Exception as exc:
            return AdapterRunResult(
                ok=False,
                command=[],
                stdout="",
                stderr=f"harness setup failed: {exc}",
                metadata={"harness_config": harness_config, "setup_error": str(exc)},
            )

        # Build the codex command
        command: list[str] = [
            "codex",
            "exec",
            "--json",
            "--dangerously-bypass-approvals-and-sandbox",
            "--dangerously-bypass-hook-trust",
            "-C", str(ctx.workspace),
            "-",
        ]

        # Read the prompt from the prompt_file
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

        # For RTK configs, prepend the system prompt
        effective_prompt = prompt_text
        if harness_config in ("rtk", "full_harness_rtk"):
            effective_prompt = f"{_RTK_SYSTEM_PROMPT}\n\n{prompt_text}"

        # Build environment
        env = os.environ.copy()
        env.update(ctx.env)

        try:
            completed = subprocess.run(
                command,
                input=effective_prompt,
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
                stderr=f"codex timed out after {ctx.timeout_sec}s",
                metadata={"harness_config": harness_config, "timeout": True},
            )

        thread_id, transcript, usage = _parse_codex_jsonl(completed.stdout)
        _save_transcript(ctx.workspace, transcript)

        return AdapterRunResult(
            ok=completed.returncode == 0,
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
            metadata={
                "returncode": completed.returncode,
                "harness_config": harness_config,
                "thread_id": thread_id,
                "transcript": transcript,
                "usage": usage,
            },
        )


def _save_transcript(workspace: Path, transcript: str) -> None:
    try:
        (workspace / ".bench_transcript.txt").write_text(transcript, encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# JSONL parsing helpers (ported from benchmark/runner/providers.py)
# ---------------------------------------------------------------------------

def _parse_codex_jsonl(output: str) -> tuple[str | None, str, dict]:
    """Parse Codex JSONL output into (thread_id, transcript, usage_dict)."""
    thread_id = None
    transcript_parts: list[str] = []
    usage = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
    }

    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if line.strip():
                transcript_parts.append(line.strip())
            continue

        etype = event.get("type")

        if etype == "thread.started":
            thread_id = event.get("thread_id") or thread_id
            continue

        if etype == "turn.completed":
            turn_usage = event.get("usage", {})
            usage["input_tokens"] += int(turn_usage.get("input_tokens", 0))
            usage["cached_input_tokens"] += int(turn_usage.get("cached_input_tokens", 0))
            usage["output_tokens"] += int(turn_usage.get("output_tokens", 0))
            usage["reasoning_output_tokens"] += int(
                turn_usage.get("reasoning_output_tokens", 0)
            )
            continue

        if etype != "item.completed":
            continue

        item = event.get("item", {})
        item_type = item.get("type", "item")

        if item_type == "agent_message" and item.get("text"):
            transcript_parts.append(f"ASSISTANT: {item['text']}")
        elif item_type == "command_execution":
            cmd_text = item.get("command", "")
            output_text = _compact_output(item.get("aggregated_output", ""))
            transcript_parts.append(f"COMMAND: {cmd_text}\nOUTPUT:\n{output_text}".strip())
        elif item_type == "error" and item.get("message"):
            transcript_parts.append(f"ERROR: {item['message']}")

    return thread_id, "\n\n".join(transcript_parts), usage


def _compact_output(output: str, max_chars: int = 1200) -> str:
    if len(output) <= max_chars:
        return output
    head = max_chars // 2
    tail = max_chars - head
    omitted = len(output) - max_chars
    return (
        f"{output[:head]}\n"
        f"... [{omitted:,} command-output characters omitted] ...\n"
        f"{output[-tail:]}"
    )
